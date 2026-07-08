import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from lib import channel as channel_lib  # noqa: E402

from app.asgi import app  # noqa: E402
from app.services import workspace_store  # noqa: E402


class TestCockpitWorkspaceEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        self.channels_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.channels_tmp.cleanup)
        channels_root = Path(self.channels_tmp.name) / "channels"
        self.slug = "testchan"
        base = channels_root / self.slug
        base.mkdir(parents=True)
        (base / "channel.json").write_text(
            json.dumps(
                {
                    "slug": self.slug,
                    "name": "Test Channel",
                    "niche": "test niche",
                    "video_language": "pt-BR",
                    "voice_name": "pt-BR-AntonioNeural-Male",
                    "paragraph_number": 2,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (base / "script_prompt.md").write_text("Explique UMA curiosidade.\n", encoding="utf-8")
        self.channels_patcher = patch.object(channel_lib, "CHANNELS_DIR", channels_root)
        self.channels_patcher.start()
        self.addCleanup(self.channels_patcher.stop)

        self.workspace_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace_tmp.cleanup)
        self.workspace_patcher = patch(
            "app.services.workspace_store._workspace_dir",
            return_value=Path(self.workspace_tmp.name),
        )
        self.workspace_patcher.start()
        self.addCleanup(self.workspace_patcher.stop)

    def test_get_workspace_seeds_from_channel_defaults(self):
        response = self.client.get("/api/v1/cockpit/workspace", params={"channel_slug": self.slug})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["script"]["paragraph_number"], 2)
        self.assertEqual(data["voice"]["voice_name"], "pt-BR-AntonioNeural-Male")

    def test_get_workspace_unknown_channel_404s(self):
        response = self.client.get("/api/v1/cockpit/workspace", params={"channel_slug": "does-not-exist"})
        self.assertEqual(response.status_code, 404)

    def test_patch_workspace_tracks_overrides(self):
        self.client.get("/api/v1/cockpit/workspace", params={"channel_slug": self.slug})
        response = self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": self.slug},
            json={"script": {"video_subject": "Something else"}},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("video_subject", data["overrides"])

    def test_reset_workspace_reapplies_channel_defaults(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": self.slug},
            json={"script": {"video_subject": "Something else"}},
        )
        response = self.client.post(
            "/api/v1/cockpit/workspace/reset", params={"channel_slug": self.slug}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["overrides"], [])

    def test_restore_field_reverts_single_field(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": self.slug},
            json={"script": {"video_subject": "Something else"}},
        )
        response = self.client.post(
            "/api/v1/cockpit/workspace/restore-field",
            params={"channel_slug": self.slug},
            json={"field_key": "video_subject"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["script"]["video_subject"], "test niche")
        self.assertNotIn("video_subject", data["overrides"])

    def test_workspace_steps_reflects_active_step_and_script_progress(self):
        response = self.client.get(
            "/api/v1/cockpit/workspace/steps", params={"channel_slug": self.slug}
        )
        self.assertEqual(response.status_code, 200)
        states = response.json()["data"]["states"]
        self.assertEqual(states[0], "active")

        workspace = workspace_store.load_workspace(self.slug)
        workspace.script.video_script = "Roteiro pronto."
        workspace.active_step = 1
        workspace_store.save_workspace(workspace)

        response = self.client.get(
            "/api/v1/cockpit/workspace/steps", params={"channel_slug": self.slug}
        )
        states = response.json()["data"]["states"]
        self.assertEqual(states[0], "done")
        self.assertEqual(states[1], "active")


if __name__ == "__main__":
    unittest.main()
