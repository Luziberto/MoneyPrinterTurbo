import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils.target_duration import (
    duration_seconds_from_target_duration,
    format_target_duration,
    paragraph_number_from_target_duration,
    parse_target_duration,
)


class TestTargetDuration(unittest.TestCase):
    def test_parse_range(self):
        self.assertEqual(parse_target_duration("60-90"), (60, 90))
        self.assertEqual(parse_target_duration("60s-90s"), (60, 90))

    def test_parse_single_value(self):
        self.assertEqual(parse_target_duration("60"), (60, 60))

    def test_format_range(self):
        self.assertEqual(format_target_duration(60, 90), "60-90")
        self.assertEqual(format_target_duration(60, 60), "60")

    def test_paragraphs_from_midpoint(self):
        self.assertEqual(paragraph_number_from_target_duration("60-90"), 3)
        self.assertEqual(paragraph_number_from_target_duration("50-50"), 2)

    def test_duration_seconds_from_range(self):
        self.assertEqual(duration_seconds_from_target_duration("60-90"), 75)


if __name__ == "__main__":
    unittest.main()
