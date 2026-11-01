import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
from urllib.error import URLError

from dotenv import dotenv_values
from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from backend import history, outages
from backend.main import app
from backend.schemas import DiagnosticResult


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.dsn = os.environ.get('TEST_DATABASE_URL') or dotenv_values(root / '.env').get('TEST_DATABASE_URL')
        if not cls.dsn:
            raise RuntimeError('TEST_DATABASE_URL is required for isolated history tests.')
        cls.schema = 'test_history_' + uuid4().hex
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        cls.test_dsn = make_conninfo(cls.dsn, options=f'-c search_path={cls.schema}')
        with psycopg.connect(cls.test_dsn) as conn:
            conn.execute((root / 'backend' / 'history.sql').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        environment = patch.dict(os.environ, {'DATABASE_URL': self.test_dsn})
        environment.start(); self.addCleanup(environment.stop)
        with psycopg.connect(self.test_dsn) as conn:
            conn.execute('DELETE FROM assistant_runs')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_started_is_committed_before_operation_and_checked_response_persists(self):
        def operation():
            rows = history.list_runs()
            self.assertEqual(rows[0]['status'], 'started')
            return {'model': 'qwen3:4b', 'answer': 'Ответ', 'mode': 'clarify', 'sources': [], 'thinking': 'private-thinking'}
        result = history.record('diagnostics', {'description': 'Вопрос'}, operation, DiagnosticResult)
        self.assertEqual(result['answer'], 'Ответ')
        rows = history.list_runs()
        self.assertEqual(rows[0]['status'], 'completed')
        self.assertEqual(rows[0]['request_data'], {'description': 'Вопрос'})
        self.assertNotIn('thinking', rows[0]['response_data'])
        self.assertIsNotNone(rows[0]['finished_at'])
        self.assertEqual(history.list_runs()[0]['id'], rows[0]['id'])

    def test_real_tool_result_is_in_history_without_creating_ticket(self):
        with patch('backend.database.create_ticket') as create:
            response = self.client.get('/api/outages/demo-north')
        self.assertEqual(response.status_code, 200)
        rows = self.client.get('/api/history').json()
        self.assertEqual(rows[0]['kind'], 'outage')
        self.assertEqual(rows[0]['response_data']['status'], 'active')
        self.assertEqual(rows[0]['response_data']['incident']['id'], 'DEMO-OUTAGE-001')
        create.assert_not_called()
        self.client.get('/api/outages/demo-center')
        latest = self.client.get('/api/history?limit=1').json()
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]['request_data']['area_code'], 'demo-center')

    def test_failed_request_stores_public_error_but_not_raw_exception(self):
        with patch('urllib.request.urlopen', side_effect=URLError('private-network-secret')):
            response = self.client.post('/api/assistant/outage', json={'question': 'Проверь аварии', 'area_code': 'demo-north'})
        self.assertEqual(response.status_code, 503)
        row = self.client.get('/api/history').json()[0]
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['error_message'], response.json()['detail'])
        self.assertNotIn('private-network-secret', str(row))

    def test_missing_history_prevents_execution_and_failed_completion_is_not_success(self):
        with patch('backend.history.get_connection', side_effect=psycopg.OperationalError('private-dsn')), patch('backend.outages.check_outage_status') as execute:
            response = self.client.get('/api/outages/demo-north')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-dsn', response.text)
        execute.assert_not_called()
        with patch('backend.history._finish', side_effect=history.HistoryUnavailableError('Не удалось подтвердить сохранение истории.')):
            response = self.client.get('/api/outages/demo-center')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(history.list_runs()[0]['status'], 'started')

    def test_invalid_requests_do_not_start_runs_and_limit_is_bounded(self):
        self.assertEqual(self.client.get('/api/outages/not-an-area').status_code, 422)
        self.assertEqual(history.list_runs(), [])
        for limit in [0, 51]:
            self.assertEqual(self.client.get(f'/api/history?limit={limit}').status_code, 422)

    def test_original_service_error_survives_a_failure_to_log_it(self):
        with patch('urllib.request.urlopen', side_effect=URLError('private-network')), \
                patch('backend.history._finish', side_effect=history.HistoryUnavailableError('История недоступна')):
            response = self.client.post('/api/assistant/outage', json={'question': 'Проверь аварии', 'area_code': 'demo-north'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('Ollama', response.json()['detail'])
        self.assertNotIn('private-network', response.text)
        self.assertEqual(history.list_runs()[0]['status'], 'started')

    def test_tool_failure_is_recorded_without_inventing_a_result(self):
        with patch('backend.outages.check_outage_status', side_effect=outages.OutageUnavailableError('Учебный статус аварий недоступен.')):
            response = self.client.get('/api/outages/demo-north')
        self.assertEqual(response.status_code, 503)
        row = history.list_runs()[0]
        self.assertEqual(row['kind'], 'outage')
        self.assertEqual(row['status'], 'failed')
        self.assertIsNone(row['response_data'])
        self.assertEqual(row['error_message'], 'Учебный статус аварий недоступен.')
