"""Tests for pipeline channel loader."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from lib import channel as channel_lib  # noqa: E402


class TestLoadChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.channels_root = Path(self.tmp.name) / "channels"
        self.slug = "testchan"
        base = self.channels_root / self.slug
        base.mkdir(parents=True)
        (base / "channel.json").write_text(
            json.dumps(
                {
                    "slug": self.slug,
                    "name": "Test Channel",
                    "niche": "test niche",
                    "video_language": "pt-BR",
                    "voice_name": "pt-BR-AntonioNeural-Male",
                    "paragraph_number": 2,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (base / "script_prompt.md").write_text(
            "Explique UMA curiosidade sobre {niche}.\n",
            encoding="utf-8",
        )
        self.patcher = patch.object(channel_lib, "CHANNELS_DIR", self.channels_root)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_load_channel_substitutes_niche(self):
        config = channel_lib.load_channel(self.slug)
        self.assertEqual(config["name"], "Test Channel")
        self.assertEqual(config["slug"], self.slug)
        self.assertIn("test niche", config["video_script_prompt"])
        self.assertNotIn("{niche}", config["video_script_prompt"])
        self.assertEqual(config["collector"]["target_clips"], 25)
        self.assertEqual(config["collector"]["min_acceptable_clips"], 20)

    def test_load_channel_normalizes_publish_profiles(self):
        base = self.channels_root / self.slug
        data = json.loads((base / "channel.json").read_text(encoding="utf-8"))
        data["publish_profiles"] = [
            {"platform": "youtube", "enabled": True, "privacy_status": "unlisted"}
        ]
        (base / "channel.json").write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )
        config = channel_lib.load_channel(self.slug)
        self.assertEqual(len(config["publish_profiles"]), 1)
        self.assertEqual(config["publish_profiles"][0]["platform"], "youtube")

    def test_load_channel_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            channel_lib.load_channel("nonexistent")

    def test_list_channels(self):
        self.assertEqual(channel_lib.list_channels(), [self.slug])


if __name__ == "__main__":
    unittest.main()
