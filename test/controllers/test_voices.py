import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402


class TestVoicesEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_list_tts_servers(self):
        response = self.client.get("/api/v1/voices/servers")
        self.assertEqual(response.status_code, 200)
        servers = response.json()["data"]["servers"]
        self.assertTrue(any(s["id"] == "azure-tts-v1" for s in servers))

    def test_list_voices_delegates_to_voice_catalog(self):
        with patch(
            "app.services.voice_catalog.list_voices",
            return_value=[{"name": "pt-BR-AntonioNeural-Male", "label": "AntonioMale"}],
        ) as mock_list:
            response = self.client.get("/api/v1/voices", params={"tts_server": "azure-tts-v1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["voices"][0]["name"], "pt-BR-AntonioNeural-Male")
        mock_list.assert_called_once_with("azure-tts-v1", elevenlabs_api_key=None)

    def test_list_fonts_returns_ttf_and_ttc_only(self):
        response = self.client.get("/api/v1/fonts")
        self.assertEqual(response.status_code, 200)
        fonts = response.json()["data"]["fonts"]
        self.assertTrue(all(f.lower().endswith((".ttf", ".ttc")) for f in fonts))

    def test_list_bgm_profiles(self):
        with patch("app.services.bgm.list_profiles", return_value=["upbeat", "calm"]):
            response = self.client.get("/api/v1/bgm-profiles")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["profiles"], ["upbeat", "calm"])


if __name__ == "__main__":
    unittest.main()
