import unittest
import psycopg
from backend.vector_store import get_search_connection


class ReaderPermissionsTests(unittest.TestCase):
    def test_web_reader_can_search_but_has_no_write_privileges(self):
        with get_search_connection() as conn:
            role = conn.execute('SELECT current_user AS name').fetchone()
            self.assertEqual(role['name'], 'knowledge_reader')
            self.assertIsNotNone(conn.execute('SELECT count(*) FROM knowledge_chunks').fetchone())
            privileges = conn.execute("SELECT has_table_privilege(current_user, 'knowledge_chunks', 'INSERT,UPDATE,DELETE,TRUNCATE') AS writes").fetchone()
            self.assertFalse(privileges['writes'])
        with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction), get_search_connection() as conn:
            conn.execute('DELETE FROM knowledge_chunks')
