import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.modes import apply_mode_defaults, supported_modes


class TestModesRegistry(unittest.TestCase):
    def test_faceless_mode_is_registered(self):
        self.assertIn("faceless", supported_modes())

    def test_apply_mode_defaults_fills_missing_fields(self):
        config = apply_mode_defaults(
            {
                "slug": "demo",
                "mode": "faceless",
                "video_source": "pexels",
            }
        )
        self.assertEqual(config["mode"], "faceless")
        self.assertEqual(config["video_source"], "pexels")
        self.assertTrue(config["match_materials_to_script"])


if __name__ == "__main__":
    unittest.main()
