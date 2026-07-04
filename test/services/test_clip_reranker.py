import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.schema import CollectorSelectedClip
from app.services import clip_reranker


class TestClipReranker(unittest.TestCase):
    def test_passthrough_when_disabled(self):
        clips = [
            CollectorSelectedClip(path="a.mp4", score=1.0),
            CollectorSelectedClip(path="b.mp4", score=9.0),
        ]
        with patch.dict(os.environ, {"MPT_RERANKER": "none"}, clear=False):
            result = clip_reranker.rerank_collector_clips(clips, keyword="tokyo")
        self.assertEqual([clip.path for clip in result], ["a.mp4", "b.mp4"])

    def test_score_ordering_when_enabled(self):
        clips = [
            CollectorSelectedClip(path="a.mp4", visual_score=1.0),
            CollectorSelectedClip(path="b.mp4", visual_score=9.0),
        ]
        with patch.dict(os.environ, {"MPT_RERANKER": "score"}, clear=False):
            result = clip_reranker.rerank_collector_clips(clips, keyword="tokyo")
        self.assertEqual(result[0].path, "b.mp4")


if __name__ == "__main__":
    unittest.main()
