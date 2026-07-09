import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402
from app.services.video_library_store import VideoLibraryStore  # noqa: E402


class DashboardSummaryTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.db_tmp.cleanup)
        self.db_patcher = patch(
            "app.services.video_library_store.default_db_path",
            return_value=Path(self.db_tmp.name) / "videos.db",
        )
        self.db_patcher.start()
        self.addCleanup(self.db_patcher.stop)
        self.store = VideoLibraryStore()

    def test_summary_shape_with_empty_library(self):
        response = self.client.get("/api/v1/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(
            set(data["status_counts"].keys()),
            {"draft", "rendering", "ready", "scheduled", "published", "archived", "failed"},
        )
        self.assertEqual(set(data["time_window_counts"].keys()), {"today", "this_week", "this_month"})
        self.assertIn("provider_health", data)
        self.assertEqual(data["recent_videos"], [])
        self.assertEqual(data["recent_errors"], [])
        self.assertIn("disk_usage", data)
        self.assertTrue(data["disk_usage"]["total"] > 0)
        self.assertEqual(data["estimated_minutes_saved"]["videos_counted"], 0)
        self.assertTrue(data["estimated_minutes_saved"]["is_estimate"])
        self.assertIn("queue", data)

    def test_status_counts_reflect_created_videos(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        self.store.create_video(id="b", channel_slug="japao", status="ready")
        self.store.create_video(id="c", channel_slug="japao", status="failed")

        response = self.client.get("/api/v1/dashboard/summary")
        data = response.json()["data"]
        self.assertEqual(data["status_counts"]["ready"], 2)
        self.assertEqual(data["status_counts"]["failed"], 1)

    def test_time_window_counts_include_just_created_video(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")

        response = self.client.get("/api/v1/dashboard/summary")
        data = response.json()["data"]
        self.assertEqual(data["time_window_counts"]["today"], 1)
        self.assertEqual(data["time_window_counts"]["this_week"], 1)
        self.assertEqual(data["time_window_counts"]["this_month"], 1)

    def test_recent_errors_only_include_failed_videos(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        self.store.create_video(id="b", channel_slug="japao", status="failed")
        self.store.update_video("b", error="boom")

        response = self.client.get("/api/v1/dashboard/summary")
        data = response.json()["data"]
        self.assertEqual(len(data["recent_errors"]), 1)
        self.assertEqual(data["recent_errors"][0]["id"], "b")
        self.assertEqual(data["recent_errors"][0]["error"], "boom")

    def test_estimated_minutes_saved_only_counts_videos_that_reached_ready(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        self.store.create_video(id="b", channel_slug="japao", status="rendering")
        self.store.create_video(id="c", channel_slug="japao", status="archived")

        response = self.client.get("/api/v1/dashboard/summary")
        data = response.json()["data"]["estimated_minutes_saved"]
        self.assertEqual(data["videos_counted"], 2)
        self.assertEqual(data["minutes"], data["minutes_per_video"] * 2)

    def test_stage_timing_averages_are_computed_from_events(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        self.store.add_event(
            video_id="a", type="stage_completed", actor="system",
            data={"stage": "render", "elapsed_seconds": 12.0},
        )
        response = self.client.get("/api/v1/dashboard/summary")
        data = response.json()["data"]
        self.assertEqual(data["stage_timing_avg_seconds"]["render"], 12.0)
        self.assertIsNone(data["stage_timing_avg_seconds"]["script"])


if __name__ == "__main__":
    unittest.main()
