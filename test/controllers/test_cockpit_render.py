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


class TestCockpitRenderEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        self.channels_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.channels_tmp.cleanup)
        channels_root = Path(self.channels_tmp.name) / "channels"
        self.slug = "testchan"
        base = channels_root / self.slug
        base.mkdir(parents=True)
        (base / "channel.json").write_text(
            json.dumps({"slug": self.slug, "name": "Test Channel", "niche": "test niche"}),
            encoding="utf-8",
        )
        (base / "script_prompt.md").write_text("Explique.\n", encoding="utf-8")
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

    def test_render_blocked_without_force(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": self.slug},
            json={"script": {"video_subject": "Kyoto"}},
        )
        # No LLM provider configured in the test config -> llm readiness is
        # blocked, so this should 400 rather than submit a task.
        response = self.client.post(
            "/api/v1/cockpit/render",
            params={"channel_slug": self.slug},
            json={"force": False},
        )
        self.assertEqual(response.status_code, 400)

    def test_render_submits_task_and_stores_task_id_when_forced(self):
        self.client.patch(
            "/api/v1/cockpit/workspace",
            params={"channel_slug": self.slug},
            json={"script": {"video_subject": "Kyoto", "video_script": "Roteiro pronto."}},
        )
        with patch("app.controllers.v1.video.task_manager.add_task") as mock_add_task:
            response = self.client.post(
                "/api/v1/cockpit/render",
                params={"channel_slug": self.slug},
                json={"force": True},
            )
        self.assertEqual(response.status_code, 200)
        mock_add_task.assert_called_once()
        called_func = mock_add_task.call_args[0][0]
        self.assertEqual(called_func.__name__, "start_with_lock")

        task_id = response.json()["data"]["task_id"]
        self.assertTrue(task_id)

        from app.services import workspace_store

        workspace = workspace_store.load_workspace(self.slug)
        self.assertEqual(workspace.render.last_render_task_id, task_id)


if __name__ == "__main__":
    unittest.main()
