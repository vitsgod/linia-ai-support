"""Existing API unit tests bypass journal I/O; test_history owns real isolated DB tests."""
import unittest
from unittest.mock import patch


class ApiUnitTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        journal = patch('backend.history.record', side_effect=lambda kind, inputs, operation, schema: operation())
        journal.start()
        self.addCleanup(journal.stop)
