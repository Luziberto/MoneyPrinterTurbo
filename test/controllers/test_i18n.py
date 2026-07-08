import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402


class TestI18nEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_known_locale_returns_translation_dict(self):
        response = self.client.get("/api/v1/i18n/pt")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("Language", data)
        self.assertIn("Translation", data)
        self.assertGreater(len(data["Translation"]), 0)

    def test_unknown_locale_404s(self):
        response = self.client.get("/api/v1/i18n/xx")
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_attempt_404s(self):
        response = self.client.get("/api/v1/i18n/..%2f..%2fconfig")
        self.assertEqual(response.status_code, 404)

    def test_all_known_locales_load(self):
        for locale in ("de", "en", "es", "id", "pt", "ru", "tr", "vi", "zh"):
            response = self.client.get(f"/api/v1/i18n/{locale}")
            self.assertEqual(response.status_code, 200, locale)


if __name__ == "__main__":
    unittest.main()
