"""Tests for topic status transitions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from lib import topics as topics_lib  # noqa: E402


class TestTopicPublishTransitions(unittest.TestCase):
    def test_mark_published_requires_approved(self):
        topic = {"id": 1, "status": "generated"}
        with self.assertRaises(ValueError):
            topics_lib.mark_published(
                topic, platforms=["youtube"], results=[{"success": True}]
            )

    def test_mark_published_from_approved(self):
        topic = {"id": 1, "status": "approved", "approved": True}
        topics_lib.mark_published(
            topic,
            platforms=["youtube"],
            results=[{"success": True, "request_id": "abc"}],
        )
        self.assertEqual(topic["status"], "published")
        self.assertIn("published_at", topic)
        self.assertEqual(topic["publish_platforms"], ["youtube"])
        self.assertEqual(topic["publish_results"][0]["request_id"], "abc")


if __name__ == "__main__":
    unittest.main()
