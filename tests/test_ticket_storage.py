import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from dotenv import dotenv_values
from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from backend.main import app


class TicketStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.dsn = os.environ.get("TEST_DATABASE_URL") or dotenv_values(root / ".env").get("TEST_DATABASE_URL")
        if not cls.dsn:
            raise RuntimeError("Run scripts/local_db.py first; TEST_DATABASE_URL is required.")
        # Every run owns its own schema. No working rows are deleted.
        cls.schema = "test_tickets_" + uuid4().hex
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.test_dsn = make_conninfo(cls.dsn, options=f"-c search_path={cls.schema}")
        with psycopg.connect(cls.test_dsn) as conn:
            conn.execute((root / "backend" / "schema.sql").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(cls.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        self.environment = patch.dict(os.environ, {"DATABASE_URL": self.test_dsn})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.ticket = {"name": "Алексей", "subject": "Нет интернета", "description": "Соединение пропало утром"}

    def test_created_ticket_is_committed_and_returned_by_list(self):
        response = self.client.post("/api/tickets", json={**self.ticket, "name": "  Алексей  "})
        self.assertEqual(response.status_code, 201, response.text)
        ticket = response.json()
        self.assertEqual(ticket["name"], "Алексей")
        self.assertEqual(ticket["status"], "Новая")
        self.assertIsInstance(ticket["id"], int)
        self.assertTrue(ticket["created_at"])
        with psycopg.connect(self.test_dsn) as conn:
            row = conn.execute("SELECT name FROM tickets WHERE id = %s", (ticket["id"],)).fetchone()
        self.assertEqual(row, ("Алексей",))
        listed = self.client.get("/api/tickets")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(ticket, listed.json())

    def test_newest_ticket_is_listed_first(self):
        first = self.client.post("/api/tickets", json=self.ticket)
        second = self.client.post("/api/tickets", json={**self.ticket, "subject": "Повторная проверка"})
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        result = self.client.get("/api/tickets").json()
        self.assertEqual(result[0]["id"], second.json()["id"])

    def test_invalid_ticket_is_not_written(self):
        with psycopg.connect(self.test_dsn) as conn:
            before = conn.execute("SELECT count(*) FROM tickets").fetchone()[0]
        response = self.client.post("/api/tickets", json={**self.ticket, "description": "   "})
        self.assertEqual(response.status_code, 422, response.text)
        with psycopg.connect(self.test_dsn) as conn:
            after = conn.execute("SELECT count(*) FROM tickets").fetchone()[0]
        self.assertEqual(after, before)

    def test_sql_like_text_is_stored_as_data(self):
        text = "O'Brien'); DROP TABLE tickets; --"
        response = self.client.post("/api/tickets", json={**self.ticket, "description": text})
        self.assertEqual(response.status_code, 201, response.text)
        with psycopg.connect(self.test_dsn) as conn:
            row = conn.execute("SELECT description FROM tickets WHERE id = %s", (response.json()["id"],)).fetchone()
        self.assertEqual(row, (text,))

    def test_unavailable_database_returns_503_without_credentials(self):
        # A real refused connection, not a mocked database response.
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:private-secret@127.0.0.1:1/unavailable"}):
            for method in ["post", "get"]:
                with self.subTest(method=method):
                    response = self.client.post("/api/tickets", json=self.ticket) if method == "post" else self.client.get("/api/tickets")
                    self.assertEqual(response.status_code, 503, response.text)
                    self.assertNotIn("private-secret", response.text)
                    self.assertNotIn("postgresql://", response.text)


if __name__ == "__main__":
    unittest.main()
