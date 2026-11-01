import io
from http.client import IncompleteRead
import json
import socket
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app

CONTEXT = {'id': 'all-devices-offline:01', 'document_id': 'all-devices-offline',
           'title': 'Нет интернета', 'section': 'Проверки', 'source': 'all-devices-offline.md',
           'text': 'Проверьте подключение кабеля.', 'score': 0.8}


def reply(answer='OK', **overrides):
    content = {'mode': 'answer', 'answer': answer, 'source_ids': [CONTEXT['id']], **overrides}
    return json.dumps({'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(content)}}).encode()


from history_helpers import ApiUnitTestCase


class DiagnosticsTests(ApiUnitTestCase):
    def setUp(self):
        super().setUp()
        retrieval = patch('backend.rag.retrieve_context', return_value=[CONTEXT])
        retrieval.start()
        self.addCleanup(retrieval.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_success_sends_trimmed_description_to_local_model(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(reply('Проверьте подключение кабеля.'))) as transport:
            response = self.client.post('/api/diagnostics', json={"description": "  Пропал интернет  "})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['answer'], 'Проверьте подключение кабеля.')
        self.assertEqual(response.json()['sources'][0]['id'], CONTEXT['id'])
        sent = transport.call_args.args[0]
        self.assertEqual(sent.full_url, 'http://127.0.0.1:11434/api/chat')
        body = json.loads(sent.data)
        self.assertEqual(body['messages'][1]['role'], 'user')
        data = json.loads(body['messages'][1]['content'])
        self.assertEqual(data['question'], 'Пропал интернет')
        self.assertEqual(data['materials'][0]['text'], CONTEXT['text'])
        self.assertIn('source_ids', body['format']['properties'])
        self.assertEqual(body['messages'][0]['role'], 'system')
        self.assertIs(body['stream'], False)
        self.assertIs(body['think'], False)

    def test_bad_inputs_never_call_model(self):
        for payload in [{}, {"description": "   "}, {"description": 123}, {"description": "я" * 5001}, {"description": "Нет сети", "url": "http://example.com"}]:
            with self.subTest(payload_type=type(payload.get('description')).__name__):
                with patch('urllib.request.urlopen') as transport:
                    response = self.client.post('/api/diagnostics', json=payload)
                self.assertEqual(response.status_code, 422, response.text)
                transport.assert_not_called()

    def test_numbers_and_punctuation_require_an_actual_description(self):
        for description in ['321', '!!!', '123-456', '😀😀']:
            with self.subTest(description=description):
                reply = io.BytesIO(b'{"done":true,"done_reason":"stop","message":{"content":"Generic advice"}}')
                with patch('urllib.request.urlopen', return_value=reply) as transport:
                    response = self.client.post('/api/diagnostics', json={"description": description})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()['detail'][0]['field'], 'description')
                self.assertIn('Опишите словами', response.json()['detail'][0]['message'])
                transport.assert_not_called()

    def test_unavailable_model_returns_503_then_slot_is_released(self):
        with patch('urllib.request.urlopen', side_effect=URLError('private-network-details')):
            response = self.client.post('/api/diagnostics', json={"description": "Нет сети"})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn('private-network-details', response.text)
        with patch('urllib.request.urlopen', return_value=io.BytesIO(reply())):
            response = self.client.post('/api/diagnostics', json={"description": "Нет сети"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_timeout_returns_504(self):
        for failure in [socket.timeout(), URLError(socket.timeout())]:
            with self.subTest(failure=type(failure).__name__), patch('urllib.request.urlopen', side_effect=failure):
                response = self.client.post('/api/diagnostics', json={"description": "Нет сети"})
            self.assertEqual(response.status_code, 504, response.text)

    def test_interrupted_response_body_returns_502(self):
        class BrokenResponse(io.BytesIO):
            def read(self, *args):
                raise IncompleteRead(b'partial', 10)

        with patch('urllib.request.urlopen', return_value=BrokenResponse()):
            response = self.client.post('/api/diagnostics', json={"description": "Нет сети"})
        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn('оборвался', response.json()['detail'])

    def test_http_error_is_reported_without_provider_details(self):
        failure = HTTPError('http://127.0.0.1:11434/api/chat', 404, 'private-provider-message', {}, io.BytesIO(b'private-body'))
        with patch('urllib.request.urlopen', side_effect=failure):
            response = self.client.post('/api/diagnostics', json={"description": "Нет сети"})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertNotIn('private-', response.text)

    def test_second_request_is_rejected_while_model_is_busy(self):
        entered, release = Event(), Event()

        def slow_transport(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise TimeoutError()
            return io.BytesIO(reply())

        with patch('urllib.request.urlopen', side_effect=slow_transport), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.client.post, '/api/diagnostics', json={"description": "Первый запрос"})
            try:
                self.assertTrue(entered.wait(3))
                second = self.client.post('/api/diagnostics', json={"description": "Второй запрос"})
                self.assertEqual(second.status_code, 503, second.text)
                self.assertIn('уже обрабатывает', second.json()['detail'])
            finally:
                release.set()
            self.assertEqual(first.result(timeout=3).status_code, 200)

    def test_invalid_and_incomplete_model_responses_return_502(self):
        for payload in [b'not-json', b'[]', b'null', b'{"done":true}', b'{"done":true,"done_reason":"length","message":{"content":"cut"}}', b'{"done":false,"message":{"content":"partial"}}', b'{"done":true,"done_reason":"stop","message":{"content":"  "}}', b'x' * 65537]:
            with self.subTest(size=len(payload)), patch('urllib.request.urlopen', return_value=io.BytesIO(payload)):
                response = self.client.post('/api/diagnostics', json={"description": "Нет сети"})
            self.assertEqual(response.status_code, 502, response.text)

    def test_unknown_empty_or_duplicate_citations_are_rejected(self):
        for overrides in [
            {'source_ids': ['invented:99']}, {'source_ids': []},
            {'source_ids': [CONTEXT['id'], CONTEXT['id']]},
            {'mode': 'clarify', 'source_ids': [CONTEXT['id']]},
        ]:
            with self.subTest(overrides=overrides), patch('urllib.request.urlopen', return_value=io.BytesIO(reply(**overrides))):
                response = self.client.post('/api/diagnostics', json={'description': 'Нет сети'})
            self.assertEqual(response.status_code, 502)
            self.assertIn('источник', response.json()['detail'])


if __name__ == '__main__':
    unittest.main()
