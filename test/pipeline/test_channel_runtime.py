import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

from lib.channel import CHANNEL_DEFAULTS, load_channel  # noqa: E402
from orchestrator import build_video_payload  # noqa: E402


class TestChannelRuntime(unittest.TestCase):
    def test_channel_defaults_include_match_materials(self):
        self.assertFalse(CHANNEL_DEFAULTS["match_materials_to_script"])

    def test_japao_channel_enables_match_materials(self):
        config = load_channel("japao")
        self.assertTrue(config["match_materials_to_script"])
        self.assertEqual(config["slug"], "japao")
        self.assertEqual(config.get("mode"), "faceless")
        self.assertTrue(config.get("title_enabled"))
        self.assertEqual(config["collector"]["target_clips"], 25)
        self.assertEqual(config["collector"]["min_acceptable_clips"], 20)

    def test_build_video_payload_forwards_match_materials(self):
        config = {
            "video_language": "pt-BR",
            "paragraph_number": 2,
            "video_source": "collector",
            "match_materials_to_script": True,
            "collector": {"target_clips": 12, "min_acceptable_clips": 10},
        }
        payload = build_video_payload(config, "Curiosidade sobre templo")
        self.assertTrue(payload["match_materials_to_script"])
        self.assertEqual(payload["video_subject"], "Curiosidade sobre templo")
        self.assertEqual(payload["collector_target_clips"], 12)
        self.assertEqual(payload["collector_min_acceptable_clips"], 10)


if __name__ == "__main__":
    unittest.main()
