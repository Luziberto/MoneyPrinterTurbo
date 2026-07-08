import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402
from app.models.schema import CollectorKeyword, NormalizedCollectorKeywords  # noqa: E402


class TestCockpitPreviewEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.workspace_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace_tmp.cleanup)
        self.workspace_patcher = patch(
            "app.services.workspace_store._workspace_dir",
            return_value=Path(self.workspace_tmp.name),
        )
        self.workspace_patcher.start()
        self.addCleanup(self.workspace_patcher.stop)

    def test_preview_rejects_empty_subject_and_script(self):
        response = self.client.post(
            "/api/v1/cockpit/preview",
            params={"channel_slug": "acme"},
            json={"include_audio": False},
        )
        self.assertEqual(response.status_code, 400)

    def test_preview_generates_script_and_terms(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": "acme"},
            json={"script": {"video_subject": "Templo em Kyoto"}},
        )
        terms = NormalizedCollectorKeywords(
            keywords=[CollectorKeyword(term="temple", weight=0.9)],
            has_explicit_weights=True,
        )
        with patch("app.services.llm.generate_script", return_value="Roteiro gerado."), patch(
            "app.services.llm.generate_terms", return_value=terms
        ):
            response = self.client.post(
                "/api/v1/cockpit/preview",
                params={"channel_slug": "acme"},
                json={"include_audio": False},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["script"]["video_script"], "Roteiro gerado.")
        self.assertEqual(data["keywords"]["terms"][0]["term"], "temple")
        self.assertTrue(data["preview"]["ready"])
        self.assertIsNotNone(data["preview"]["last_preview_at"])

    def test_preview_propagates_script_generation_error(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": "acme"},
            json={"script": {"video_subject": "Templo em Kyoto"}},
        )
        with patch("app.services.llm.generate_script", return_value="Error: boom"):
            response = self.client.post(
                "/api/v1/cockpit/preview",
                params={"channel_slug": "acme"},
                json={"include_audio": False},
            )
        self.assertEqual(response.status_code, 400)

    def test_preview_with_audio_returns_audio_url(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": "acme"},
            json={"script": {"video_subject": "Templo em Kyoto"}},
        )
        terms = NormalizedCollectorKeywords(keywords=[], has_explicit_weights=False)

        def fake_tts(text, voice_name, voice_rate, voice_file, voice_volume=1.0):
            Path(voice_file).write_bytes(b"fake-mp3")
            return MagicMock()

        with patch("app.services.llm.generate_script", return_value="Roteiro gerado."), patch(
            "app.services.llm.generate_terms", return_value=terms
        ), patch("app.services.voice.tts", side_effect=fake_tts):
            response = self.client.post(
                "/api/v1/cockpit/preview",
                params={"channel_slug": "acme"},
                json={"include_audio": True},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIsNotNone(data["preview"]["last_preview_audio_file"])
        self.assertIn("preview_audio_url", data)

        audio_response = self.client.get(data["preview_audio_url"])
        self.assertEqual(audio_response.status_code, 200)

        from app.utils import utils

        Path(utils.storage_dir("temp"), data["preview"]["last_preview_audio_file"]).unlink(
            missing_ok=True
        )

    def test_get_providers_readiness(self):
        response = self.client.get(
            "/api/v1/cockpit/providers", params={"video_source": "pexels", "voice_name": ""}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("llm", data)
        self.assertIn("status", data["llm"])

    def test_get_runtime_limits(self):
        response = self.client.get("/api/v1/cockpit/runtime-limits")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("max_threads", data)
        self.assertIsNone(data["lock"])

    def test_clear_lock_noop_when_no_lock(self):
        response = self.client.post("/api/v1/cockpit/runtime-limits/clear-lock", json={"force": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["cleared"])


if __name__ == "__main__":
    unittest.main()
