import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402
from app.services.video_library_store import VideoLibraryStore  # noqa: E402
from app.utils import utils  # noqa: E402


class VideosLibraryEndpointsTestCase(unittest.TestCase):
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

    def _task_dir_cleanup(self, task_id: str):
        self.addCleanup(shutil.rmtree, utils.task_dir(task_id), ignore_errors=True)

    def test_list_videos_filters_by_status(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        self.store.create_video(id="b", channel_slug="japao", status="failed")

        response = self.client.get("/api/v1/video-library", params={"status": "ready"})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["videos"][0]["id"], "a")

    def test_list_videos_rejects_invalid_status(self):
        response = self.client.get("/api/v1/video-library", params={"status": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_get_detail_includes_publications_assets_and_script(self):
        task_id = "task-detail"
        self._task_dir_cleanup(task_id)
        task_dir = utils.task_dir(task_id)
        with open(os.path.join(task_dir, "final-1.mp4"), "wb") as f:
            f.write(b"videobytes")
        with open(os.path.join(task_dir, "script.json"), "w", encoding="utf-8") as f:
            json.dump({"script": "Ola", "search_terms": [], "params": {}}, f)

        self.store.create_video(id=task_id, channel_slug="japao", status="ready")
        self.store.create_publication(video_id=task_id, platform="tiktok", provider="zernio")

        response = self.client.get(f"/api/v1/video-library/{task_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["publications"]), 1)
        self.assertEqual(data["script"]["script"], "Ola")
        self.assertTrue(any(a["kind"] == "video" for a in data["assets"]))

    def test_get_detail_404_for_missing_video(self):
        response = self.client.get("/api/v1/video-library/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_patch_updates_metadata_and_writes_event(self):
        self.store.create_video(id="a", channel_slug="japao")
        response = self.client.patch(
            "/api/v1/video-library/a", json={"title": "New", "tags": ["x"], "caption": "cap"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["title"], "New")
        self.assertEqual(data["tags"], ["x"])
        self.assertEqual(data["caption"], "cap")
        events = self.store.list_events("a")
        self.assertEqual(events[0]["type"], "title_changed")

    def test_patch_with_no_fields_is_a_noop(self):
        self.store.create_video(id="a", channel_slug="japao", title="Original")
        response = self.client.patch("/api/v1/video-library/a", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["title"], "Original")
        self.assertEqual(self.store.list_events("a"), [])

    def test_delete_removes_row_and_task_directory(self):
        task_id = "task-delete"
        task_dir = utils.task_dir(task_id)
        with open(os.path.join(task_dir, "final-1.mp4"), "wb") as f:
            f.write(b"x")
        self.store.create_video(id=task_id, channel_slug="japao")

        response = self.client.delete(f"/api/v1/video-library/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.store.get_video(task_id))
        self.assertFalse(os.path.exists(task_dir))

    def test_publish_now_creates_one_publication_per_platform_with_shared_result(self):
        task_id = "task-publish"
        self._task_dir_cleanup(task_id)
        video_path = os.path.join(utils.task_dir(task_id), "final-1.mp4")
        with open(video_path, "wb") as f:
            f.write(b"x")
        self.store.create_video(id=task_id, channel_slug="japao", status="ready")
        self.store.update_video(task_id, video_path=video_path)

        with patch(
            "app.services.publish.cross_post_videos",
            return_value=[{"success": True, "post_id": "p1"}],
        ) as mock_publish:
            response = self.client.post(
                f"/api/v1/video-library/{task_id}/publish",
                json={"platforms": ["tiktok", "youtube"]},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["video"]["status"], "published")
        self.assertEqual(len(data["publications"]), 2)
        for pub in data["publications"]:
            self.assertEqual(pub["status"], "published")
            self.assertEqual(pub["url"], "p1")
        self.assertEqual(mock_publish.call_args.kwargs["platforms"], ["tiktok", "youtube"])

    def test_publish_now_marks_publications_failed_on_backend_failure(self):
        task_id = "task-publish-fail"
        self._task_dir_cleanup(task_id)
        video_path = os.path.join(utils.task_dir(task_id), "final-1.mp4")
        with open(video_path, "wb") as f:
            f.write(b"x")
        self.store.create_video(id=task_id, channel_slug="japao", status="ready")
        self.store.update_video(task_id, video_path=video_path)

        with patch(
            "app.services.publish.cross_post_videos",
            return_value=[{"success": False, "error": "quota exceeded"}],
        ):
            response = self.client.post(
                f"/api/v1/video-library/{task_id}/publish", json={"platforms": ["tiktok"]}
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["video"]["status"], "ready")
        self.assertEqual(data["publications"][0]["status"], "failed")
        self.assertEqual(data["publications"][0]["error"], "quota exceeded")

    def test_publish_now_rejects_invalid_platform(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        response = self.client.post(
            "/api/v1/video-library/a/publish", json={"platforms": ["myspace"]}
        )
        self.assertEqual(response.status_code, 400)

    def test_publish_now_rejects_when_video_file_missing(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        response = self.client.post(
            "/api/v1/video-library/a/publish", json={"platforms": ["tiktok"]}
        )
        self.assertEqual(response.status_code, 400)

    def test_schedule_creates_publications_and_rolls_up_status(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        response = self.client.post(
            "/api/v1/video-library/a/schedule",
            json={"platforms": ["tiktok", "instagram"], "scheduled_at": "2099-01-01T00:00:00+00:00"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["video"]["status"], "scheduled")
        self.assertEqual(len(data["publications"]), 2)

    def test_cancel_publication(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        pub = self.store.create_publication(video_id="a", platform="tiktok", provider="zernio")
        response = self.client.post(f"/api/v1/video-library/a/publications/{pub['id']}/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "cancelled")

    def test_cancel_publication_404_when_pub_belongs_to_different_video(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        self.store.create_video(id="b", channel_slug="japao", status="ready")
        pub = self.store.create_publication(video_id="b", platform="tiktok", provider="zernio")
        response = self.client.post(f"/api/v1/video-library/a/publications/{pub['id']}/cancel")
        self.assertEqual(response.status_code, 404)

    def test_archive_then_restore(self):
        self.store.create_video(id="a", channel_slug="japao", status="ready")
        response = self.client.post("/api/v1/video-library/a/archive")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "archived")

        response = self.client.post("/api/v1/video-library/a/restore")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ready")

    def test_archive_rejects_invalid_status(self):
        self.store.create_video(id="a", channel_slug="japao", status="rendering")
        response = self.client.post("/api/v1/video-library/a/archive")
        self.assertEqual(response.status_code, 400)

    def test_re_render_submits_new_task_and_links_event(self):
        task_id = "task-original"
        self._task_dir_cleanup(task_id)
        with open(os.path.join(utils.task_dir(task_id), "script.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "script": "Ola",
                    "search_terms": [],
                    "params": {"video_subject": "Kyoto", "video_script": "Ola", "script_mode": "verbatim"},
                },
                f,
            )
        self.store.create_video(id=task_id, channel_slug="japao", status="ready", source="cockpit")

        with patch("app.controllers.v1.video.task_manager.add_task") as mock_add_task:
            response = self.client.post(f"/api/v1/video-library/{task_id}/re-render")
        self.assertEqual(response.status_code, 200)
        new_task_id = response.json()["data"]["task_id"]
        self.assertNotEqual(new_task_id, task_id)
        self.addCleanup(shutil.rmtree, utils.task_dir(new_task_id), ignore_errors=True)

        mock_add_task.assert_called_once()
        self.assertEqual(mock_add_task.call_args[0][0].__name__, "start_and_track_library")

        events = self.store.list_events(task_id)
        self.assertEqual(events[0]["type"], "re_rendered")
        self.assertEqual(events[0]["data"]["new_video_id"], new_task_id)

        # The new task also gets a library row, created with source carried
        # over from the original video (not hardcoded to "api").
        new_video = self.store.get_video(new_task_id)
        self.assertIsNotNone(new_video)
        self.assertEqual(new_video["source"], "cockpit")

    def test_re_render_400_when_no_script_json(self):
        self.store.create_video(id="task-no-script", channel_slug="japao", status="ready")
        response = self.client.post("/api/v1/video-library/task-no-script/re-render")
        self.assertEqual(response.status_code, 400)

    def test_run_due_publications_endpoint_returns_processed_list(self):
        response = self.client.post("/api/v1/video-library/run-due-publications")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["processed"], [])


if __name__ == "__main__":
    unittest.main()
