import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.video_library_scheduler import run_due_publications
from app.services.video_library_store import VideoLibraryStore
from app.utils import utils


class VideoLibrarySchedulerTestCase(unittest.TestCase):
    def setUp(self):
        self.db_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.db_tmp.cleanup)
        self.store = VideoLibraryStore(Path(self.db_tmp.name) / "videos.db")

    def _make_video_with_file(self, video_id: str, status: str = "scheduled") -> str:
        task_dir = utils.task_dir(video_id)
        self.addCleanup(shutil.rmtree, task_dir, ignore_errors=True)
        video_path = os.path.join(task_dir, "final-1.mp4")
        with open(video_path, "wb") as f:
            f.write(b"x")
        self.store.create_video(id=video_id, channel_slug="japao", status=status)
        self.store.update_video(video_id, video_path=video_path)
        return video_path

    def test_no_due_publications_returns_empty_list(self):
        with patch("app.services.video_library_store.default_db_path", return_value=self.store.db_path):
            self.assertEqual(run_due_publications(), [])

    def test_publishes_due_scheduled_publication_and_syncs_status(self):
        self._make_video_with_file("v1")
        self.store.create_publication(
            video_id="v1", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2020-01-01T00:00:00+00:00",
        )

        with patch("app.services.video_library_store.default_db_path", return_value=self.store.db_path), \
             patch(
                "app.services.publish.cross_post_videos",
                return_value=[{"success": True, "post_id": "abc"}],
             ) as mock_publish:
            processed = run_due_publications()

        self.assertEqual(len(processed), 1)
        self.assertTrue(processed[0]["success"])
        video = self.store.get_video("v1")
        self.assertEqual(video["status"], "published")
        mock_publish.assert_called_once()

        events = self.store.list_events("v1")
        self.assertTrue(any(e["actor"] == "scheduler" for e in events))

    def test_marks_publication_failed_when_video_file_missing_from_disk(self):
        self.store.create_video(id="v2", channel_slug="japao", status="scheduled")
        # video_path never set -- simulates a video row whose file was deleted
        pub = self.store.create_publication(
            video_id="v2", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2020-01-01T00:00:00+00:00",
        )

        with patch("app.services.video_library_store.default_db_path", return_value=self.store.db_path):
            processed = run_due_publications()

        self.assertEqual(len(processed), 1)
        self.assertFalse(processed[0]["success"])
        self.assertEqual(self.store.get_publication(pub["id"])["status"], "failed")

    def test_backend_exception_marks_all_due_publications_failed_without_aborting_scan(self):
        self._make_video_with_file("v3")
        self.store.create_publication(
            video_id="v3", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2020-01-01T00:00:00+00:00",
        )

        with patch("app.services.video_library_store.default_db_path", return_value=self.store.db_path), \
             patch("app.services.publish.cross_post_videos", side_effect=RuntimeError("network down")):
            processed = run_due_publications()

        self.assertEqual(len(processed), 1)
        self.assertFalse(processed[0]["success"])

    def test_groups_multiple_due_platforms_for_same_video_into_one_publish_call(self):
        self._make_video_with_file("v4")
        self.store.create_publication(
            video_id="v4", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2020-01-01T00:00:00+00:00",
        )
        self.store.create_publication(
            video_id="v4", platform="youtube", provider="zernio", status="scheduled",
            scheduled_at="2020-01-01T00:00:00+00:00",
        )

        with patch("app.services.video_library_store.default_db_path", return_value=self.store.db_path), \
             patch(
                "app.services.publish.cross_post_videos",
                return_value=[{"success": True}],
             ) as mock_publish:
            processed = run_due_publications()

        self.assertEqual(len(processed), 2)
        mock_publish.assert_called_once()
        self.assertEqual(sorted(mock_publish.call_args.kwargs["platforms"]), ["tiktok", "youtube"])

    def test_publications_not_yet_due_are_left_untouched(self):
        self._make_video_with_file("v5")
        self.store.create_publication(
            video_id="v5", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2099-01-01T00:00:00+00:00",
        )

        with patch("app.services.video_library_store.default_db_path", return_value=self.store.db_path):
            processed = run_due_publications()

        self.assertEqual(processed, [])
        self.assertEqual(self.store.get_video("v5")["status"], "scheduled")


if __name__ == "__main__":
    unittest.main()
