import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from backend.embeddings import EmbeddingError, embed_documents, embed_query


class EmbeddingTests(unittest.TestCase):
    def reply(self, vectors):
        return io.BytesIO(json.dumps({'embeddings': vectors}).encode())

    def test_documents_are_sent_without_query_instruction_and_normalized(self):
        vector = [3.0, 4.0] + [0.0] * 1022
        with patch('urllib.request.urlopen', return_value=self.reply([vector])) as transport:
            result = embed_documents(['Текст инструкции'])
        self.assertAlmostEqual(result[0][0], 0.6)
        self.assertAlmostEqual(result[0][1], 0.8)
        self.assertEqual(len(result[0]), 1024)
        outgoing = transport.call_args.args[0]
        self.assertEqual(outgoing.full_url, 'http://127.0.0.1:11434/api/embed')
        self.assertEqual(json.loads(outgoing.data)['input'], ['Текст инструкции'])
        self.assertIs(json.loads(outgoing.data)['truncate'], False)

    def test_query_gets_instruction_prefix(self):
        with patch('urllib.request.urlopen', return_value=self.reply([[1.0] + [0.0] * 1023])) as transport:
            embed_query('  Ноутбук не подключается  ')
        body = json.loads(transport.call_args.args[0].data)
        self.assertTrue(body['input'][0].startswith('Instruct:'))
        self.assertTrue(body['input'][0].endswith('Query: Ноутбук не подключается'))

    def test_invalid_vectors_are_rejected(self):
        for vector in [[], [1.0, 2.0], [0.0] * 1024, [float('nan')] + [0.0] * 1023, ['1'] + [0.0] * 1023, [True] + [0.0] * 1023]:
            with self.subTest(first=vector[:2]), patch('urllib.request.urlopen', return_value=self.reply([vector])):
                with self.assertRaises(EmbeddingError):
                    embed_documents(['Документ'])

    def test_missing_or_wrong_count_response_is_rejected(self):
        for reply in [b'[]', b'not-json', b'{"embeddings":[]}', b'{"embeddings":null}']:
            with self.subTest(reply=reply), patch('urllib.request.urlopen', return_value=io.BytesIO(reply)):
                with self.assertRaises(EmbeddingError):
                    embed_documents(['Документ'])

    def test_network_error_and_empty_input_have_readable_failures(self):
        with patch('urllib.request.urlopen', side_effect=URLError('private-details')):
            with self.assertRaises(EmbeddingError) as caught:
                embed_query('Нет сети')
        self.assertNotIn('private-details', str(caught.exception))
        with patch('urllib.request.urlopen') as transport:
            for inputs in [[], [''], ['   ']]:
                with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                    embed_documents(inputs)
            transport.assert_not_called()
