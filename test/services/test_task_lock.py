import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import const  # noqa: E402
from app.models.schema import VideoParams  # noqa: E402
from app.services import state as sm  # noqa: E402
from app.services import task as tm  # noqa: E402


class TestStartWithLock(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patcher = patch(
            "app.services.runtime_limits.runtime_dir",
            return_value=Path(self._tmp.name),
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_non_video_stop_at_bypasses_lock(self):
        with patch("app.services.task.start", return_value={"ok": True}) as mock_start:
            result = tm.start_with_lock("task-1", VideoParams(video_subject="x"), stop_at="script")
        mock_start.assert_called_once()
        self.assertEqual(result, {"ok": True})

    def test_second_concurrent_video_render_fails_with_lock_conflict(self):
        release_first = threading.Event()
        first_acquired = threading.Event()

        def slow_start(task_id, params, stop_at):
            first_acquired.set()
            release_first.wait(timeout=2)
            return {"task_id": task_id}

        with patch("app.services.task.start", side_effect=slow_start):
            thread = threading.Thread(
                target=tm.start_with_lock,
                args=("task-first", VideoParams(video_subject="x"), "video"),
            )
            thread.start()
            self.assertTrue(first_acquired.wait(timeout=2))

            # Second render attempts to acquire the same global lock while
            # the first is still "running" -- must fail, not silently overlap.
            tm.start_with_lock("task-second", VideoParams(video_subject="y"), "video")

            release_first.set()
            thread.join(timeout=2)

        second_state = sm.state.get_task("task-second")
        self.assertIsNotNone(second_state)
        self.assertEqual(second_state["state"], const.TASK_STATE_FAILED)
        self.assertIn("already running", second_state.get("error", ""))

        sm.state.delete_task("task-first")
        sm.state.delete_task("task-second")


class TestStartAndTrackLibrary(unittest.TestCase):
    def setUp(self):
        self._runtime_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._runtime_tmp.cleanup)
        self._lock_patcher = patch(
            "app.services.runtime_limits.runtime_dir",
            return_value=Path(self._runtime_tmp.name),
        )
        self._lock_patcher.start()
        self.addCleanup(self._lock_patcher.stop)

        self._db_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._db_tmp.cleanup)
        self._db_patcher = patch(
            "app.services.video_library_store.default_db_path",
            return_value=Path(self._db_tmp.name) / "videos.db",
        )
        self._db_patcher.start()
        self.addCleanup(self._db_patcher.stop)

        from app.services.video_library_store import VideoLibraryStore

        self.library_store = VideoLibraryStore()
        self.addCleanup(sm.state.delete_task, "task-lib")

    def test_syncs_completed_render_to_ready_with_thumbnail_and_stats(self):
        self.library_store.create_video(id="task-lib", channel_slug="japao")
        sm.state.update_task(
            "task-lib",
            state=const.TASK_STATE_COMPLETE,
            videos=["/tasks/task-lib/final-1.mp4"],
            terms=[{"term": "kyoto", "weight": 1.0}],
            thumbnail_path="/tasks/task-lib/final-1-thumbnail.jpg",
            video_duration_seconds=42.0,
            video_file_size_bytes=999,
        )

        with patch(
            "app.services.task.start",
            return_value={"task_id": "task-lib"},
        ):
            tm.start_and_track_library("task-lib", VideoParams(video_subject="Kyoto"), stop_at="video")

        video = self.library_store.get_video("task-lib")
        self.assertEqual(video["status"], "ready")
        self.assertEqual(video["thumbnail_path"], "/tasks/task-lib/final-1-thumbnail.jpg")
        self.assertEqual(video["duration_seconds"], 42.0)
        self.assertEqual(video["file_size_bytes"], 999)
        self.assertEqual(video["keywords"], [{"term": "kyoto", "weight": 1.0}])

    def test_syncs_failed_render_to_failed_with_error(self):
        self.library_store.create_video(id="task-lib", channel_slug="japao")
        sm.state.update_task("task-lib", state=const.TASK_STATE_FAILED, error="tts failed")

        with patch("app.services.task.start", return_value=None):
            tm.start_and_track_library("task-lib", VideoParams(video_subject="Kyoto"), stop_at="video")

        video = self.library_store.get_video("task-lib")
        self.assertEqual(video["status"], "failed")
        self.assertEqual(video["error"], "tts failed")

    def test_sync_is_a_noop_when_no_library_row_exists(self):
        # No create_video() call -- mirrors /subtitle and /audio tasks, which
        # never get a library row, and must not crash when synced anyway.
        sm.state.update_task("task-lib", state=const.TASK_STATE_COMPLETE, videos=[])
        with patch("app.services.task.start", return_value={"task_id": "task-lib"}):
            tm.start_and_track_library("task-lib", VideoParams(video_subject="x"), stop_at="video")
        self.assertIsNone(self.library_store.get_video("task-lib"))

    def test_sync_runs_even_when_start_with_lock_raises(self):
        self.library_store.create_video(id="task-lib", channel_slug="japao")

        def boom(task_id, params, stop_at):
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED, error="boom")
            raise RuntimeError("boom")

        with patch("app.services.task.start", side_effect=boom):
            with self.assertRaises(RuntimeError):
                tm.start_and_track_library("task-lib", VideoParams(video_subject="x"), stop_at="video")

        video = self.library_store.get_video("task-lib")
        self.assertEqual(video["status"], "failed")


if __name__ == "__main__":
    unittest.main()
