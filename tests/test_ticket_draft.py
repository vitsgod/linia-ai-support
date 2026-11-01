import io
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app


def reply(data):
    return io.BytesIO(json.dumps({'done': True, 'done_reason': 'stop',
        'message': {'content': json.dumps(data)}}).encode())


from history_helpers import ApiUnitTestCase


class TicketDraftTests(ApiUnitTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_known_vague_description_is_clarified_before_generation(self):
        with patch('urllib.request.urlopen', return_value=reply({'mode': 'draft', 'draft': {'subject': 'x', 'description': 'y'}})) as transport:
            response = self.client.post('/api/assistant/ticket-draft', json={'description': 'ничего не работает'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'clarify')
        self.assertIsNone(response.json()['model'])
        transport.assert_not_called()

    def test_draft_is_not_saved_and_name_is_not_generated(self):
        decision = {'mode': 'draft', 'draft': {'subject': 'Нет интернета на ноутбуке', 'description': 'На телефоне интернет есть, на ноутбуке нет.'}}
        with patch('urllib.request.urlopen', return_value=reply(decision)) as transport, \
                patch('backend.database.create_ticket') as create:
            response = self.client.post('/api/assistant/ticket-draft', json={'description': '  На телефоне интернет есть, на ноутбуке нет.  '})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIs(response.json()['saved'], False)
        self.assertEqual(response.json()['draft'], decision['draft'])
        self.assertNotIn('name', response.json()['draft'])
        create.assert_not_called()
        body = json.loads(transport.call_args.args[0].data)
        self.assertNotIn('tools', body)
        self.assertIn('format', body)

    def test_clarify_and_invalid_model_output_do_not_create_anything(self):
        for decision in [
            {'mode': 'draft', 'draft': None},
            {'mode': 'clarify', 'draft': {'subject': 'x', 'description': 'y'}},
            {'mode': 'draft', 'draft': {'subject': '', 'description': 'y'}},
            {'mode': 'draft', 'draft': {'subject': 'x', 'description': 'y', 'name': 'Придуманное имя'}},
            {'mode': 'draft', 'draft': {'subject': 'x', 'description': 'y'}, 'saved': True},
        ]:
            with patch('urllib.request.urlopen', return_value=reply(decision)), patch('backend.database.create_ticket') as create:
                response = self.client.post('/api/assistant/ticket-draft', json={'description': 'Нет интернета'})
            self.assertEqual(response.status_code, 502, response.text)
            create.assert_not_called()
        with patch('urllib.request.urlopen', return_value=reply({'mode': 'clarify', 'draft': None})):
            response = self.client.post('/api/assistant/ticket-draft', json={'description': 'Привет'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['draft'])
        self.assertIs(response.json()['saved'], False)

    def test_invalid_input_never_calls_model_and_timeout_releases_slot(self):
        with patch('urllib.request.urlopen') as transport:
            for payload in [{}, {'description': ' '}, {'description': '321'}, {'description': 'x' * 5001}, {'description': 'Нет сети', 'save': True}]:
                self.assertEqual(self.client.post('/api/assistant/ticket-draft', json=payload).status_code, 422)
            transport.assert_not_called()
        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            self.assertEqual(self.client.post('/api/assistant/ticket-draft', json={'description': 'Нет сети'}).status_code, 504)
        with patch('urllib.request.urlopen', return_value=reply({'mode': 'clarify', 'draft': None})):
            self.assertEqual(self.client.post('/api/assistant/ticket-draft', json={'description': 'Привет'}).status_code, 200)
