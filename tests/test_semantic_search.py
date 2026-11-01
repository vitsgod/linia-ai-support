import unittest

from backend.knowledge import KnowledgeChunk
from backend.semantic_search import cosine_similarity, rank_chunks


class SemanticSearchTests(unittest.TestCase):
    def test_cosine_known_cases_are_not_length_dependent(self):
        self.assertAlmostEqual(cosine_similarity([2, 0], [5, 0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [-1, 0]), -1.0)
        self.assertAlmostEqual(cosine_similarity([3, 4], [1, 0]), 0.6)

    def test_invalid_dimensions_and_zero_vectors_fail(self):
        for first, second in [([], []), ([1], [1, 2]), ([0, 0], [1, 0]), ([float('inf')], [1])]:
            with self.subTest(first=first), self.assertRaises(ValueError):
                cosine_similarity(first, second)

    def test_ranking_keeps_source_metadata(self):
        chunks = [
            KnowledgeChunk('wifi:01', 'wifi', 'Wi-Fi', 'Проверки', 'wifi.md', 'Текст Wi-Fi', 'Учебная'),
            KnowledgeChunk('cable:01', 'cable', 'Кабель', 'Проверки', 'cable.md', 'Текст кабель', 'Учебная'),
        ]
        result = rank_chunks(chunks, [[0, 1], [1, 0]], [2, 0], limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['chunk'].id, 'cable:01')
        self.assertEqual(result[0]['chunk'].source, 'cable.md')
        self.assertAlmostEqual(result[0]['score'], 1.0)
        with self.assertRaises(ValueError):
            rank_chunks(chunks, [[1, 0]], [1, 0])
