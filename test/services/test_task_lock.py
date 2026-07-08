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


if __name__ == "__main__":
    unittest.main()
