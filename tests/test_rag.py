import unittest
from unittest.mock import patch

from backend import ai, rag
from fastapi.testclient import TestClient
from backend.main import app
from backend.embeddings import EmbeddingError
import psycopg

ROW = {'id': 'one-device-offline:01', 'document_id': 'one-device-offline',
       'title': 'Одно устройство', 'section': 'Проверки', 'source': 'one-device-offline.md',
       'text': 'Телефон работает, проверьте подключение ноутбука.', 'score': 0.7}


from history_helpers import ApiUnitTestCase


class RagTests(ApiUnitTestCase):
    def test_known_vague_descriptions_do_not_retrieve_or_generate(self):
        with patch('backend.rag.retrieve_context') as retrieve, patch('backend.ai.diagnose') as generate:
            for description in ['ничего не работает', 'У меня всё сломалось!', 'Помогите, оно не открывается']:
                self.assertEqual(rag.diagnose(description)['mode'], 'clarify')
            retrieve.assert_not_called()
            generate.assert_not_called()
        self.assertFalse(rag.needs_subject('Интернет не работает на телефоне'))
        self.assertFalse(rag.needs_subject('Ничего не работает на ноутбуке'))

    def test_empty_and_low_similarity_never_generate(self):
        for rows in [[], [{**ROW, 'score': 0.318}]]:
            with patch('backend.rag.retrieve_context', return_value=rows), patch('backend.ai.diagnose') as generate:
                result = rag.diagnose('Как приготовить борщ?')
            generate.assert_not_called()
            self.assertEqual(result['mode'], 'clarify')
            self.assertEqual(result['sources'], [])
            self.assertIsNone(result['model'])

    def test_only_cited_and_passed_sources_are_exposed(self):
        with patch('backend.rag.retrieve_context', return_value=[ROW]), patch('backend.ai.diagnose',
                return_value={'model': ai.MODEL, 'answer': 'Проверьте ноутбук.', 'mode': 'answer', 'source_ids': [ROW['id']]}):
            result = rag.diagnose('Телефон работает, ноутбук нет')
        self.assertEqual(result['sources'][0]['excerpt'], ROW['text'])
        self.assertEqual(result['sources'][0]['url'], '/api/knowledge/one-device-offline.md')

    def test_model_clarification_cannot_expose_irrelevant_advice(self):
        with patch('backend.rag.retrieve_context', return_value=[ROW]), patch('backend.ai.diagnose',
                return_value={'model': ai.MODEL, 'answer': 'Выдуманные советы', 'mode': 'clarify', 'source_ids': []}):
            result = rag.diagnose('Привет')
        self.assertNotIn('Выдуманные', result['answer'])
        self.assertEqual(result['sources'], [])

    def test_unavailable_dependencies_have_safe_api_errors(self):
        with TestClient(app) as client:
            for failure in [EmbeddingError('private-host'), psycopg.OperationalError('private-secret')]:
                with patch('backend.rag.retrieve_context', side_effect=failure):
                    response = client.post('/api/diagnostics', json={'description': 'Нет интернета'})
                self.assertEqual(response.status_code, 503)
                self.assertNotIn('private-', response.text)
                self.assertNotIn('сохранить заявку', response.json()['detail'])

    def test_document_routes_only_serve_known_markdown(self):
        with TestClient(app) as client:
            response = client.get('/api/knowledge/one-device-offline.md')
            self.assertEqual(response.status_code, 200)
            self.assertIn('Учебная инструкция', response.text)
            for name in ['.env', 'missing.md', 'ai.py']:
                self.assertEqual(client.get('/api/knowledge/' + name).status_code, 404)
