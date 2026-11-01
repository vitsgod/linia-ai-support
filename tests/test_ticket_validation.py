import unittest

from fastapi.testclient import TestClient

from backend.main import app


class TicketValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.ticket = {
            "name": "Алексей",
            "subject": "Нет интернета",
            "description": "Соединение пропало утром",
        }

    def tearDown(self):
        self.client.close()

    def assert_invalid(self, response, field, message_part):
        self.assertEqual(response.status_code, 422, response.text)
        errors = response.json()["detail"]
        self.assertTrue(
            any(e["field"] == field and message_part in e["message"] for e in errors),
            errors,
        )

    def test_valid_input_is_trimmed_and_explicitly_not_saved(self):
        response = self.client.post("/api/tickets/validate", json={
            "name": "  Алексей  ",
            "subject": "  Нет интернета\n",
            "description": "\tСоединение пропало утром  ",
        })
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["ticket"], self.ticket)
        self.assertIs(data["saved"], False)
        self.assertIn("не сохранена", data["message"])
        self.assertNotIn("id", data["ticket"])

    def test_blank_and_missing_fields_are_rejected(self):
        for field in self.ticket:
            for value in ["", " \t\n "]:
                with self.subTest(field=field, value=value):
                    response = self.client.post("/api/tickets/validate", json={**self.ticket, field: value})
                    self.assert_invalid(response, field, "Введите")
            with self.subTest(field=field, missing=True):
                data = {k: v for k, v in self.ticket.items() if k != field}
                self.assert_invalid(self.client.post("/api/tickets/validate", json=data), field, "Введите")

    def test_limits_apply_after_trimming(self):
        for field, limit in [("name", 100), ("subject", 200), ("description", 5000)]:
            with self.subTest(field=field):
                response = self.client.post("/api/tickets/validate", json={**self.ticket, field: "  " + "я" * limit + "  "})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["ticket"][field], "я" * limit)
                response = self.client.post("/api/tickets/validate", json={**self.ticket, field: "я" * (limit + 1)})
                self.assert_invalid(response, field, str(limit))

    def test_non_string_fields_are_rejected(self):
        for field in self.ticket:
            for value in [None, 123, True, [], {}]:
                with self.subTest(field=field, value=value):
                    self.assert_invalid(
                        self.client.post("/api/tickets/validate", json={**self.ticket, field: value}),
                        field, "строкой",
                    )

    def test_extra_fields_are_rejected(self):
        response = self.client.post("/api/tickets/validate", json={**self.ticket, "status": "closed"})
        self.assert_invalid(response, "status", "Лишнее поле")

    def test_non_object_bodies_are_rejected(self):
        for value in [[], "text", 123]:
            with self.subTest(value=value):
                self.assert_invalid(self.client.post("/api/tickets/validate", json=value), "body", "объект")

    def test_missing_body_is_rejected(self):
        self.assert_invalid(self.client.post("/api/tickets/validate"), "body", "объект")

    def test_malformed_json_is_rejected(self):
        response = self.client.post("/api/tickets/validate", content='{"name":', headers={"Content-Type": "application/json"})
        self.assert_invalid(response, "body", "JSON")


if __name__ == "__main__":
    unittest.main()
