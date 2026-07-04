import sys
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from lib.categories import topic_distribution_for_channel
from scripts.generate_topics import build_topic_records


class EditorialOverridesTestCase(unittest.TestCase):
    def test_topic_distribution_accepts_valid_channel_overrides(self) -> None:
        distribution = topic_distribution_for_channel(
            {
                "culture": 20,
                "sociedade": 7,
                "history": 0,
                "invalid": 99,
            }
        )

        self.assertEqual(distribution["culture"], 20)
        self.assertEqual(distribution["society"], 7)
        self.assertNotIn("history", distribution)
        self.assertNotIn("invalid", distribution)

    def test_build_topic_records_uses_music_profile_overrides(self) -> None:
        records = build_topic_records(
            [{"category": "food", "topic": "Por que o ramen varia por região?"}],
            music_profile_overrides={"food": ["documentary"]},
        )

        self.assertEqual(records[0]["music_profiles"], ["documentary"])


if __name__ == "__main__":
    unittest.main()
