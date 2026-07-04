import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.models.schema import CollectorJobRequest, CollectorJobResult
from app.services import collector_client


class TestCollectorClient(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_proxy_config = dict(config.proxy)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.proxy.clear()
        config.proxy.update(self.original_proxy_config)

    def test_check_collector_health_success(self):
        config.app["collector_base_url"] = "http://collector:8090"
        fake_response = SimpleNamespace(status_code=200, json=lambda: {"status": "ok"})

        with patch(
            "app.services.collector_client.requests.get", return_value=fake_response
        ) as get:
            self.assertTrue(collector_client.check_collector_health())

        self.assertEqual(get.call_args.args[0], "http://collector:8090/health")

    def test_check_collector_health_missing_base_url(self):
        config.app.pop("collector_base_url", None)
        self.assertFalse(collector_client.check_collector_health())

    def test_search_collector_clips_maps_list_response(self):
        config.app["collector_base_url"] = "http://collector:8090"
        config.app["collector_search_limit"] = 5
        fake_response = SimpleNamespace(
            status_code=200,
            json=lambda: [
                {
                    "clip_id": "abc123",
                    "title": "Taiyaki street vendor",
                    "local_path": "/data/downloads/taiyaki.mp4",
                    "duration": 12.4,
                    "width": 1080,
                    "height": 1920,
                    "source_site": "storyblocks",
                }
            ],
        )

        with patch(
            "app.services.collector_client.requests.get", return_value=fake_response
        ) as get:
            results = collector_client.search_collector_clips("taiyaki")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["clip_id"], "abc123")
        self.assertIn("q=taiyaki", get.call_args.args[0])
        self.assertIn("limit=5", get.call_args.args[0])

    def test_search_collector_clips_returns_empty_on_error(self):
        config.app["collector_base_url"] = "http://collector:8090"
        fake_response = SimpleNamespace(status_code=500, text="boom")

        with patch(
            "app.services.collector_client.requests.get", return_value=fake_response
        ):
            results = collector_client.search_collector_clips("taiyaki")

        self.assertEqual(results, [])

    def test_create_stock_job_posts_typed_payload(self):
        config.app["collector_base_url"] = "http://collector:8090"
        fake_response = SimpleNamespace(
            status_code=202,
            json=lambda: {"job_id": "job-123", "status": "pending"},
        )

        payload = CollectorJobRequest(
            client_task_id="mpt_123",
            keywords=["tokyo street"],
            target_clips=25,
            min_acceptable_clips=20,
        )
        with patch(
            "app.services.collector_client.requests.post", return_value=fake_response
        ) as post:
            result = collector_client.create_stock_job(payload)

        self.assertEqual(result.job_id, "job-123")
        self.assertEqual(result.status, "pending")
        self.assertEqual(post.call_args.args[0], "http://collector:8090/stock/jobs")
        self.assertEqual(post.call_args.kwargs["json"]["client_task_id"], "mpt_123")

    def test_wait_for_stock_job_returns_ready_result(self):
        pending = CollectorJobResult(job_id="job-123", status="pending")
        ready = CollectorJobResult(job_id="job-123", status="ready")

        with patch.object(
            collector_client,
            "get_stock_job",
            side_effect=[pending, ready],
        ), patch("app.services.collector_client.time.sleep", return_value=None):
            result = collector_client.wait_for_stock_job(
                "job-123", timeout=2, poll_interval=0.01
            )

        self.assertEqual(result.status, "ready")

    def test_wait_for_stock_job_times_out(self):
        pending = CollectorJobResult(job_id="job-123", status="pending")

        with patch.object(
            collector_client, "get_stock_job", return_value=pending
        ), patch(
            "app.services.collector_client.time.monotonic",
            side_effect=[0.0, 0.0, 1.0],
        ), patch("app.services.collector_client.time.sleep", return_value=None):
            with self.assertRaises(collector_client.CollectorTimeoutError) as ctx:
                collector_client.wait_for_stock_job(
                    "job-123", timeout=0.5, poll_interval=0.01
                )

        self.assertEqual(ctx.exception.code, "COLLECTOR_TIMEOUT")

    def test_load_selected_clips_reads_inline_response(self):
        response = CollectorJobResult(
            job_id="job-123",
            status="ready",
            selected_clips=[
                {
                    "path": "/data/downloads/a.mp4",
                    "score": 0.8,
                    "retrieval_score": 0.7,
                    "visual_score": 0.9,
                    "duration": 12.0,
                    "matched_keyword": "tokyo street",
                    "source": "magnific",
                    "width": 1280,
                    "height": 720,
                }
            ],
        )

        clips = collector_client.load_selected_clips(response)

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].path, "/data/downloads/a.mp4")

    def test_load_selected_clips_reads_file_when_needed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clips_file = Path(temp_dir) / "selected_clips.json"
            clips_file.write_text(
                '[{"path": "/data/downloads/a.mp4", "score": 0.8, '
                '"retrieval_score": 0.7, "visual_score": 0.9, "duration": 12.0, '
                '"matched_keyword": "tokyo street", "source": "magnific", '
                '"width": 1280, "height": 720}]',
                encoding="utf-8",
            )
            response = CollectorJobResult(
                job_id="job-123",
                status="ready",
                clips_file=str(clips_file),
            )

            clips = collector_client.load_selected_clips(response)

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].matched_keyword, "tokyo street")


if __name__ == "__main__":
    unittest.main()
