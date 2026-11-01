import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from fastapi.testclient import TestClient
from backend.main import app
from backend import outages, rag


def envelope(calls=None, content=''):
    return io.BytesIO(json.dumps({'done': True, 'done_reason': 'stop',
                                  'message': {'content': content, 'tool_calls': calls}}).encode())


def call(area='demo-north', name='check_outage_status', **extra):
    return {'function': {'name': name, 'arguments': {'area_code': area, **extra}}}


from history_helpers import ApiUnitTestCase


class OutageAssistantTests(ApiUnitTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.input = {'question': 'Проверь аварии в выбранном районе', 'area_code': 'demo-north'}

    def test_native_call_executes_function_and_uses_real_result_for_all_areas(self):
        for area, status in [('demo-north', 'active'), ('demo-center', 'clear'), ('demo-south', 'unknown')]:
            with patch('urllib.request.urlopen', return_value=envelope([call(area)])) as transport:
                response = self.client.post('/api/assistant/outage', json={**self.input, 'area_code': area})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result['mode'], 'tool_result')
            self.assertEqual(result['tool_name'], 'check_outage_status')
            self.assertEqual(result['tool_result']['status'], status)
            self.assertEqual(result['answer'], result['tool_result']['area_name'] + '. ' + result['tool_result']['message'])
            sent = json.loads(transport.call_args.args[0].data)
            self.assertEqual(sent['tools'][0]['function']['parameters']['properties']['area_code']['enum'], [area])
            self.assertIs(sent['think'], False)

    def test_model_text_without_tool_call_cannot_claim_an_outage(self):
        with patch('urllib.request.urlopen', return_value=envelope(content='Я обнаружил настоящую аварию')):
            response = self.client.post('/api/assistant/outage', json=self.input)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'clarify')
        self.assertIsNone(response.json()['tool_result'])
        self.assertNotIn('обнаружил', response.json()['answer'])

    def test_missing_area_does_not_call_model(self):
        with patch('urllib.request.urlopen') as transport:
            response = self.client.post('/api/assistant/outage', json={'question': 'Есть авария?'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('район', response.json()['answer'])
        transport.assert_not_called()

    def test_unapproved_calls_are_rejected_before_any_execution(self):
        for calls in [[call(name='create_ticket')], [call('demo-center')], [call(url='http://example.com')],
                      [call('unknown')], [call(), call()], 'not-a-list', [{'function': {'name': 'check_outage_status', 'arguments': '{}'}}]]:
            with self.subTest(calls=calls), patch('urllib.request.urlopen', return_value=envelope(calls)), \
                    patch('backend.outages.check_outage_status') as execute:
                response = self.client.post('/api/assistant/outage', json=self.input)
            self.assertEqual(response.status_code, 502, response.text)
            execute.assert_not_called()

    def test_validation_and_dependency_errors_are_safe(self):
        with patch('urllib.request.urlopen') as transport:
            for payload in [{}, {'question': ' '}, {'question': 'x' * 1001}, {**self.input, 'area_code': 'real-address'}, {**self.input, 'command': 'anything'}]:
                self.assertEqual(self.client.post('/api/assistant/outage', json=payload).status_code, 422)
            transport.assert_not_called()
        with patch('urllib.request.urlopen', side_effect=URLError('private-network')):
            response = self.client.post('/api/assistant/outage', json=self.input)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-network', response.text)
        with patch('urllib.request.urlopen', return_value=envelope([call()])), \
                patch('backend.outages.check_outage_status', side_effect=outages.OutageUnavailableError('Учебный статус временно недоступен.')):
            response = self.client.post('/api/assistant/outage', json=self.input)
        self.assertEqual(response.status_code, 503)

    def test_timeout_releases_slot_and_shared_pipeline_rejects_parallel_work(self):
        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            response = self.client.post('/api/assistant/outage', json=self.input)
        self.assertEqual(response.status_code, 504)
        with patch('urllib.request.urlopen', return_value=envelope()):
            self.assertEqual(self.client.post('/api/assistant/outage', json=self.input).status_code, 200)
        self.assertTrue(rag.pipeline_slot.acquire(blocking=False))
        try:
            with patch('urllib.request.urlopen') as transport:
                response = self.client.post('/api/assistant/outage', json=self.input)
            self.assertEqual(response.status_code, 503)
            transport.assert_not_called()
        finally:
            rag.pipeline_slot.release()
