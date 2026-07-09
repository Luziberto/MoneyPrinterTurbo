import os
import tempfile
import types
import unittest
from unittest.mock import patch

from app.services import thumbnail


class ThumbnailTestCase(unittest.TestCase):
    def test_extract_thumbnail_returns_false_when_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "thumb.jpg")
            self.assertFalse(
                thumbnail.extract_thumbnail(os.path.join(tmp, "missing.mp4"), output)
            )

    def test_extract_thumbnail_succeeds_on_first_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "video.mp4")
            output = os.path.join(tmp, "thumb.jpg")
            with open(video_path, "wb") as f:
                f.write(b"fake video bytes")

            def fake_run(command, capture_output, text, check, timeout):
                with open(output, "wb") as f:
                    f.write(b"fake jpeg bytes")
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(thumbnail.subprocess, "run", side_effect=fake_run) as run:
                self.assertTrue(thumbnail.extract_thumbnail(video_path, output, offset_seconds=2.0))
            self.assertEqual(run.call_count, 1)
            self.assertTrue(os.path.isfile(output))

    def test_extract_thumbnail_retries_at_zero_offset_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "video.mp4")
            output = os.path.join(tmp, "thumb.jpg")
            with open(video_path, "wb") as f:
                f.write(b"fake video bytes")

            calls = []

            def fake_run(command, capture_output, text, check, timeout):
                offset = command[command.index("-ss") + 1]
                calls.append(offset)
                if offset == "2.0":
                    return types.SimpleNamespace(returncode=1, stdout="", stderr="too short")
                with open(output, "wb") as f:
                    f.write(b"fake jpeg bytes")
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(thumbnail.subprocess, "run", side_effect=fake_run):
                self.assertTrue(thumbnail.extract_thumbnail(video_path, output, offset_seconds=2.0))
            self.assertEqual(calls, ["2.0", "0"])

    def test_extract_thumbnail_returns_false_when_both_attempts_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "video.mp4")
            output = os.path.join(tmp, "thumb.jpg")
            with open(video_path, "wb") as f:
                f.write(b"fake video bytes")

            def fake_run(command, capture_output, text, check, timeout):
                return types.SimpleNamespace(returncode=1, stdout="", stderr="broken")

            with patch.object(thumbnail.subprocess, "run", side_effect=fake_run):
                self.assertFalse(thumbnail.extract_thumbnail(video_path, output, offset_seconds=2.0))
            self.assertFalse(os.path.isfile(output))

    def test_extract_thumbnail_handles_ffmpeg_binary_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "video.mp4")
            output = os.path.join(tmp, "thumb.jpg")
            with open(video_path, "wb") as f:
                f.write(b"fake video bytes")

            with patch.object(thumbnail.subprocess, "run", side_effect=OSError("no such binary")):
                self.assertFalse(thumbnail.extract_thumbnail(video_path, output))


if __name__ == "__main__":
    unittest.main()
