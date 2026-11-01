import os
import unittest
from unittest.mock import patch
from backend import vector_store


class ContainerConfigTests(unittest.TestCase):
    def test_vector_owner_connection_can_be_configured_without_local_secret_file(self):
        dsn = 'host=db dbname=knowledge user=owner password=test'
        with patch.dict(os.environ, {'VECTOR_DATABASE_URL': dsn}), patch('backend.vector_store.psycopg.connect') as connect:
            vector_store.get_vector_connection()
        self.assertTrue(bool(connect.call_args.args) and connect.call_args.args[0] == dsn)

    def test_search_uses_reader_dsn_and_forces_read_only(self):
        reader = 'host=db dbname=knowledge user=reader password=test'
        with patch.dict(os.environ, {'VECTOR_DATABASE_URL': 'host=admin', 'VECTOR_SEARCH_URL': reader}), \
                patch('backend.vector_store.psycopg.connect') as connect:
            vector_store.get_search_connection()
        self.assertTrue(bool(connect.call_args.args) and connect.call_args.args[0] == reader)
        self.assertIn('default_transaction_read_only=on', connect.call_args.kwargs['options'])
