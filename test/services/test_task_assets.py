import os
import shutil
import unittest

from app.services import task_assets
from app.utils import utils


class TaskAssetsTestCase(unittest.TestCase):
    def setUp(self):
        self.task_id = utils.get_uuid()
        self.task_dir = utils.task_dir(self.task_id)
        self.addCleanup(shutil.rmtree, self.task_dir, ignore_errors=True)

    def _write(self, name: str, content: bytes = b"x"):
        path = os.path.join(self.task_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_find_returns_none_when_nothing_on_disk(self):
        self.assertIsNone(task_assets.find(self.task_id, "video"))

    def test_find_returns_none_for_unknown_kind(self):
        self.assertIsNone(task_assets.find(self.task_id, "not-a-kind"))

    def test_find_locates_video_by_glob_pattern(self):
        self._write("final-1.mp4", b"videobytes")
        asset = task_assets.find(self.task_id, "video")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.kind, "video")
        self.assertEqual(asset.name, "final-1.mp4")
        self.assertEqual(asset.size_bytes, len(b"videobytes"))
        self.assertIn(self.task_id, asset.url)
        self.assertIn("final-1.mp4", asset.url)

    def test_find_locates_thumbnail_regardless_of_extension(self):
        self._write("final-1-thumbnail.jpg", b"jpgbytes")
        asset = task_assets.find(self.task_id, "thumbnail")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.name, "final-1-thumbnail.jpg")

    def test_find_locates_audio(self):
        self._write("audio.mp3", b"audiobytes")
        asset = task_assets.find(self.task_id, "audio")
        self.assertEqual(asset.name, "audio.mp3")

    def test_find_locates_subtitle_in_subfolder(self):
        self._write("subtitles/subtitle.srt", b"subbytes")
        asset = task_assets.find(self.task_id, "subtitle")
        self.assertIsNotNone(asset)
        self.assertTrue(asset.name.endswith("subtitle.srt"))

    def test_find_locates_script(self):
        self._write("script.json", b"{}")
        asset = task_assets.find(self.task_id, "script")
        self.assertEqual(asset.name, "script.json")

    def test_list_assets_returns_only_kinds_present_on_disk(self):
        self._write("final-1.mp4", b"videobytes")
        self._write("script.json", b"{}")
        assets = task_assets.list_assets(self.task_id)
        kinds = {a.kind for a in assets}
        self.assertEqual(kinds, {"video", "script"})

    def test_list_assets_returns_empty_list_for_empty_task_dir(self):
        self.assertEqual(task_assets.list_assets(self.task_id), [])


if __name__ == "__main__":
    unittest.main()
