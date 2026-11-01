from datetime import datetime
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import outages
from backend.main import app


from history_helpers import ApiUnitTestCase


class OutageToolTests(ApiUnitTestCase):
    def test_three_known_areas_have_distinct_meanings(self):
        with TestClient(app) as client:
            for code, expected in [('demo-north', 'active'), ('demo-center', 'clear'), ('demo-south', 'unknown')]:
                response = client.get('/api/outages/' + code)
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['area_code'], code)
                self.assertIs(result['demo'], True)
                self.assertIsNotNone(datetime.fromisoformat(result['checked_at']).tzinfo)
                if expected == 'active':
                    self.assertEqual(result['incident']['id'], 'DEMO-OUTAGE-001')
                    self.assertIn('не указан', result['message'])
                else:
                    self.assertIsNone(result['incident'])
        self.assertIn('не доказывает', outages.check_outage_status('demo-center').message)
        self.assertIn('нет данных', outages.check_outage_status('demo-south').message)

    def test_unknown_area_is_rejected_before_tool_execution(self):
        with TestClient(app) as client, patch('backend.outages.check_outage_status') as tool:
            response = client.get('/api/outages/real-home-address')
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail'][0]['field'], 'area_code')
        tool.assert_not_called()
        with self.assertRaises(ValueError):
            outages.check_outage_status('../.env')

    def test_missing_or_invalid_source_is_unavailable_not_clear(self):
        invalid = ['not-json', '[]', '{"demo-north":{"status":"active","incident":null}}',
                   '{"demo-center":{"status":"clear","incident":{"id":"x","title":"y"}}}']
        with tempfile.TemporaryDirectory() as directory, TestClient(app) as client:
            path = Path(directory) / 'private-catalog.json'
            with patch('backend.outages.DATA_FILE', path):
                for content in [None, *invalid]:
                    if content is not None:
                        path.write_text(content, encoding='utf-8')
                    response = client.get('/api/outages/demo-center')
                    self.assertEqual(response.status_code, 503, response.text)
                    self.assertNotIn('private-catalog', response.text)
                    self.assertNotIn('clear', response.text)

    def test_reading_does_not_change_source_or_call_model_or_create_ticket(self):
        before = hashlib.sha256(outages.DATA_FILE.read_bytes()).hexdigest()
        with TestClient(app) as client, patch('backend.database.create_ticket') as create, \
                patch('backend.ai.diagnose') as generate:
            self.assertEqual(client.get('/api/outages/demo-north').status_code, 200)
        self.assertEqual(hashlib.sha256(outages.DATA_FILE.read_bytes()).hexdigest(), before)
        create.assert_not_called()
        generate.assert_not_called()
