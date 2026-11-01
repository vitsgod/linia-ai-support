import unittest
import uuid
from dataclasses import replace

from backend.knowledge import KnowledgeChunk
from backend import vector_store as store
from psycopg import sql


def vector(x, y=0):
    return [x, y] + [0.0] * 1022


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = store.get_vector_connection()
        self.schema = 'test_vectors_' + uuid.uuid4().hex
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
        self.conn.commit()
        store.init_store(self.conn)
        self.a = KnowledgeChunk('a:01', 'a', 'Первый', 'Раздел', 'a.md', 'Текст А', '')
        self.b = KnowledgeChunk('b:01', 'b', 'Второй', 'Раздел', 'b.md', 'Текст Б', '')

    def tearDown(self):
        self.conn.rollback()
        self.conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.conn.commit()
        self.conn.close()

    def test_persistent_search_orders_known_vectors_and_preserves_source(self):
        store.replace_index(self.conn, [self.a, self.b], [vector(1), vector(0, 1)])
        rows = store.search_index(self.conn, vector(1))
        self.assertEqual([r['id'] for r in rows], ['a:01', 'b:01'])
        self.assertAlmostEqual(rows[0]['score'], 1)
        self.assertAlmostEqual(rows[1]['score'], 0)
        self.assertEqual(rows[0]['source'], 'a.md')
        self.assertEqual(rows[0]['text'], self.a.text)
        store.replace_index(self.conn, [self.b], [vector(0, 1)])
        self.assertEqual(len(store.search_index(self.conn, vector(1))), 1)

    def test_failed_reindex_keeps_previous_committed_rows(self):
        store.replace_index(self.conn, [self.a], [vector(1)])
        with self.assertRaises(Exception):
            store.replace_index(self.conn, [replace(self.b, title=None)], [vector(0, 1)])
        self.assertEqual(store.search_index(self.conn, vector(1))[0]['id'], 'a:01')

    def test_invalid_vectors_and_empty_index_do_not_replace_previous_data(self):
        store.replace_index(self.conn, [self.a], [vector(1)])
        for chunks, vectors in [([], []), ([self.b], [[1, 2]]), ([self.b], [vector(float('nan'))])]:
            with self.assertRaises(ValueError):
                store.replace_index(self.conn, chunks, vectors)
        self.assertEqual(store.search_index(self.conn, vector(1))[0]['id'], 'a:01')

    def test_empty_or_different_model_index_does_not_return_candidates(self):
        self.assertEqual(store.search_index(self.conn, vector(1)), [])
        store.replace_index(self.conn, [self.a], [vector(1)])
        self.conn.execute("UPDATE knowledge_chunks SET model = 'other-model'")
        self.conn.commit()
        self.assertEqual(store.search_index(self.conn, vector(1)), [])
