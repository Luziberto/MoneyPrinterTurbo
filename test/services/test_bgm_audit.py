import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if "loguru" not in sys.modules:
    sys.modules["loguru"] = MagicMock()

from app.services import bgm_audit


class TestBgmAudit(unittest.TestCase):
    def test_record_and_read_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            task_id = "11111111-1111-1111-1111-111111111111"
            task_dir = Path(tmpdir) / "tasks" / task_id
            task_dir.mkdir(parents=True)
            output_file = str(task_dir / "final-1.mp4")
            params = SimpleNamespace(
                bgm_type="random",
                bgm_file="",
                bgm_profile="",
            )
            with patch("app.services.bgm_audit.utils.task_dir", return_value=str(task_dir)):
                bgm_audit.record_bgm_failure(
                    output_file=output_file,
                    reason="corrupt mp3",
                    params=params,
                )
                payload = bgm_audit.read_bgm_failure(task_id)
            self.assertIsNotNone(payload)
            self.assertEqual(payload["reason"], "corrupt mp3")

    def test_skips_when_bgm_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            task_id = "22222222-2222-2222-2222-222222222222"
            task_dir = Path(tmpdir) / "tasks" / task_id
            task_dir.mkdir(parents=True)
            params = SimpleNamespace(bgm_type="", bgm_file="", bgm_profile="")
            with patch("app.services.bgm_audit.utils.task_dir", return_value=str(task_dir)):
                bgm_audit.record_bgm_failure(
                    output_file=str(task_dir / "final-1.mp4"),
                    reason="ignored",
                    params=params,
                )
                self.assertIsNone(bgm_audit.read_bgm_failure(task_id))


if __name__ == "__main__":
    unittest.main()
