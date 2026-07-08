import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402


class TestPublishEndpoints(unittest.TestCase):
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

    def test_get_publish_status(self):
        response = self.client.get("/api/v1/publish/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("backend", data)
        self.assertIn("configured", data)

    def test_create_publish_returns_results(self):
        fake_results = [{"success": True, "platform": "youtube"}]
        with patch("app.services.publish.cross_post_videos", return_value=fake_results) as mock_cross_post:
            response = self.client.post(
                "/api/v1/publish",
                json={
                    "video_paths": ["/tasks/abc/final-1.mp4"],
                    "subject": "Templo em Kyoto",
                    "platforms": ["youtube"],
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["results"], fake_results)
        mock_cross_post.assert_called_once()

    def test_create_publish_saves_workspace_snapshot_when_channel_given(self):
        fake_results = [{"success": True}]
        with patch("app.services.publish.cross_post_videos", return_value=fake_results):
            self.client.post(
                "/api/v1/publish",
                params={"channel_slug": "acme"},
                json={"video_paths": ["/tasks/abc/final-1.mp4"], "subject": "Kyoto"},
            )

        from app.services import workspace_store

        workspace = workspace_store.load_workspace("acme")
        self.assertTrue(workspace.publish.done)
        self.assertEqual(workspace.publish.last_results, fake_results)


if __name__ == "__main__":
    unittest.main()
