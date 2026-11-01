import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend import answer_quality as quality, rag, ai
from backend.main import app


from history_helpers import ApiUnitTestCase


class AnswerQualityTests(ApiUnitTestCase):
    def test_saved_model_failure_is_detected(self):
        description = 'Пропал интернет на всех устройствах, кабели проверены, перезагрузка не помогла'
        answer = ('Проверьте, подключены ли сетевые кабели и не отошли ли разъёмы, '
                  'не разбирая оборудование. Уточните, включён ли роутер и есть ли питание.')
        self.assertEqual(quality.repeated_checks(description, answer), {'cables'})

    def test_explicit_completed_checks_in_both_word_orders(self):
        for text, expected in [
            ('Кабели проверены, перезагрузка не помогла', {'cables', 'router_restart'}),
            ('Я уже проверил кабель и перезагрузил роутер', {'cables', 'router_restart'}),
            ('Роутер перезапускала. Кабель я проверяла.', {'cables', 'router_restart'}),
            ('Кабель проверен', {'cables'}),
        ]:
            with self.subTest(text=text):
                self.assertEqual(quality.completed_checks(text), expected)

    def test_not_done_questions_conditionals_and_other_device_are_not_facts(self):
        for text in ['Кабели ещё не проверял', 'Я не проверял кабели',
                     'Роутер не перезагружал', 'Не перезапускал роутер',
                     'Стоит ли проверить кабель и перезагрузить роутер?',
                     'Если перезагружал роутер, что дальше?',
                     'Перезагрузил ноутбук, интернета нет']:
            with self.subTest(text=text):
                self.assertEqual(quality.completed_checks(text), set())

    def test_recommendations_are_detected_but_acknowledgements_and_prohibitions_are_not(self):
        text = 'Кабели проверены. Роутер уже перезагружал.'
        for advice in ['Проверьте кабели. Перезагрузите роутер.',
                       'Кабели нужно проверить. Попробуйте перезапустить роутер.',
                       'Убедитесь, что сетевые кабели подключены. Повторите перезагрузку роутера.']:
            with self.subTest(advice=advice):
                self.assertEqual(quality.repeated_checks(text, advice), {'cables', 'router_restart'})
        self.assertEqual(quality.repeated_checks(text, 'Уточните, подключены ли сетевые кабели и не отошли ли разъёмы.'), {'cables'})
        self.assertEqual(quality.repeated_checks(text, 'Проверьте, включены ли роутер и устройства, подключены ли сетевые кабели, не отошли ли разъёмы.'), {'cables'})
        for advice in ['Кабели уже проверены, роутер перезагружен. Уточните индикацию.',
                       'Не проверяйте кабели повторно. Не перезагружайте роутер снова.',
                       'Проверять кабели не нужно. Перезагружать роутер не надо.',
                       'Проверьте индикацию, кабели уже проверены.',
                       'Перезагрузите ноутбук, роутер не трогайте.',
                       'Проверьте, включён ли Wi-Fi на ноутбуке.']:
            with self.subTest(advice=advice):
                self.assertEqual(quality.repeated_checks(text, advice), set())

    def test_api_blocks_repeated_advice_without_creating_a_ticket(self):
        row = {'id': 'all-devices-offline:02', 'document_id': 'all-devices-offline',
               'title': 'Нет интернета', 'section': 'Проверки', 'source': 'all-devices-offline.md',
               'text': 'Проверьте кабели.', 'score': 0.8}
        generated = {'model': ai.MODEL, 'mode': 'answer', 'answer': 'Проверьте кабели.', 'source_ids': [row['id']]}
        with TestClient(app) as client, patch('backend.rag.retrieve_context', return_value=[row]), \
                patch('backend.ai.diagnose', return_value=generated), patch('backend.database.create_ticket') as create:
            response = client.post('/api/diagnostics', json={'description': 'Интернет не работает, кабели проверены'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'clarify')
        self.assertEqual(response.json()['sources'], [])
        self.assertIn('индикатор', response.json()['answer'])
        self.assertNotEqual(response.json()['answer'], generated['answer'])
        create.assert_not_called()
