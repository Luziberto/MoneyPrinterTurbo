import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402
from app.models.schema import CollectorJobResult, CollectorSelectedClip  # noqa: E402
from app.services.collector_client import CollectorError  # noqa: E402


class TestCollectorEndpoints(unittest.TestCase):
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

    def test_health_reports_unhealthy_without_network(self):
        with patch("app.services.collector_client.check_collector_health", return_value=False):
            response = self.client.get("/api/v1/collector/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["healthy"])

    def test_create_job_rejects_empty_keywords(self):
        response = self.client.post(
            "/api/v1/collector/jobs",
            json={"keywords": [], "target_clips": 25, "min_acceptable_clips": 20},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_job_returns_202_with_job_id(self):
        fake_result = CollectorJobResult(job_id="job-123", status="pending")
        with patch("app.services.collector_client.create_stock_job", return_value=fake_result):
            response = self.client.post(
                "/api/v1/collector/jobs",
                json={
                    "keywords": [{"term": "temple", "weight": 0.8}],
                    "target_clips": 25,
                    "min_acceptable_clips": 20,
                },
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["job_id"], "job-123")

    def test_create_job_maps_collector_error_to_502(self):
        with patch(
            "app.services.collector_client.create_stock_job",
            side_effect=CollectorError("COLLECTOR_DOWN", "unreachable"),
        ):
            response = self.client.post(
                "/api/v1/collector/jobs",
                json={
                    "keywords": [{"term": "temple", "weight": 0.8}],
                    "target_clips": 25,
                    "min_acceptable_clips": 20,
                },
            )
        self.assertEqual(response.status_code, 502)

    def test_get_job_saves_snapshot_into_workspace_when_ready(self):
        clip = CollectorSelectedClip(path="/data/downloads/a.mp4", source="collector")
        fake_result = CollectorJobResult(
            job_id="job-123",
            status="ready",
            selected_clips_count=1,
            local_reused=1,
            new_downloads=0,
            selected_clips=[clip],
        )
        with patch("app.services.collector_client.get_stock_job", return_value=fake_result):
            response = self.client.get(
                "/api/v1/collector/jobs/job-123", params={"channel_slug": "acme"}
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["cache_hit_pct"], 100)

        from app.services import workspace_store

        workspace = workspace_store.load_workspace("acme")
        self.assertEqual(workspace.media.last_collector_job["job_id"], "job-123")
        self.assertEqual(len(workspace.media.video_clips), 1)

    def test_get_job_does_not_touch_workspace_when_pending(self):
        fake_result = CollectorJobResult(job_id="job-123", status="pending")
        with patch("app.services.collector_client.get_stock_job", return_value=fake_result):
            response = self.client.get(
                "/api/v1/collector/jobs/job-123", params={"channel_slug": "acme"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["cache_hit_pct"])


if __name__ == "__main__":
    unittest.main()
