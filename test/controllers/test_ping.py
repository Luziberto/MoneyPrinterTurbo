import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient

from app.asgi import app


class TestPing(unittest.TestCase):
    def test_ping_returns_pong(self):
        client = TestClient(app)
        response = client.get("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), "pong")


if __name__ == "__main__":
    unittest.main()
