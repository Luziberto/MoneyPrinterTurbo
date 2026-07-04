import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.runtime_limits import (
    GenerationAlreadyRunningError,
    cap_thread_count,
    clear_stale_generation_lock,
    generation_lock_status,
    get_runtime_limits,
    single_flight_generation_lock,
)


class TestRuntimeLimits(unittest.TestCase):
    def test_cap_thread_count_respects_env(self):
        with patch.dict(os.environ, {"MPT_MAX_THREADS": "2"}, clear=False):
            self.assertEqual(cap_thread_count(8), 2)

    def test_generation_lock_single_flight(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "app.services.runtime_limits.runtime_dir",
                return_value=Path(tmpdir),
            ):
                clear_stale_generation_lock(force=True)
                with single_flight_generation_lock("task-a"):
                    self.assertIsNotNone(generation_lock_status())
                    with self.assertRaises(GenerationAlreadyRunningError):
                        with single_flight_generation_lock("task-b"):
                            pass
                self.assertIsNone(generation_lock_status())

    def test_get_runtime_limits_defaults(self):
        limits = get_runtime_limits()
        self.assertGreaterEqual(limits.max_threads, 1)
        self.assertGreater(limits.generation_lock_ttl_seconds, 0)


if __name__ == "__main__":
    unittest.main()
