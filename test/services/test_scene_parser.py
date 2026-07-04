import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import scene_parser


class TestSceneParser(unittest.TestCase):
    def test_splits_three_paragraphs_into_intro_body_cta(self):
        script = "Hook line.\n\nBody detail.\n\nSubscribe now."
        scenes = scene_parser.parse_script_scenes(script)
        self.assertEqual([scene["role"] for scene in scenes], ["intro", "body", "cta"])

    def test_reads_labeled_sections(self):
        script = "Intro: Japan trains are silent.\n\nCTA: Follow for more."
        scenes = scene_parser.parse_script_scenes(script)
        roles = {scene["role"] for scene in scenes}
        self.assertIn("intro", roles)
        self.assertIn("cta", roles)


if __name__ == "__main__":
    unittest.main()
