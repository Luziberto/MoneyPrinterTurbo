"""Tests for publish profile resolution."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from lib.publish_profiles import (  # noqa: E402
    resolve_config_publish_platforms,
    resolve_publish_platforms,
)


class TestPublishProfiles(unittest.TestCase):
    def test_publish_profiles_youtube_only(self):
        platforms, skipped, privacy = resolve_publish_platforms(
            {
                "publish_profiles": [
                    {"platform": "youtube", "enabled": True, "privacy_status": "unlisted"},
                    {"platform": "tiktok", "enabled": False},
                    {
                        "platform": "facebook",
                        "enabled": True,
                        "note": "unsupported by Upload-Post",
                    },
                ]
            }
        )
        self.assertEqual(platforms, ["youtube"])
        self.assertEqual(privacy, "unlisted")
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["platform"], "facebook")

    def test_legacy_platform_targets_fallback(self):
        platforms, skipped, privacy = resolve_publish_platforms(
            {
                "platform_targets": ["youtube", "tiktok", "facebook"],
            }
        )
        self.assertEqual(platforms, ["youtube", "tiktok"])
        self.assertIsNone(privacy)
        self.assertEqual(skipped[0]["platform"], "facebook")

    @patch("app.services.upload_post._upload_post_setting")
    def test_config_publish_platforms_youtube_only(self, mock_setting):
        def _get(key, default=None):
            values = {
                "upload_post_platforms": ["youtube", "tiktok", "instagram"],
                "upload_post_youtube_privacy_status": "unlisted",
            }
            return values.get(key, default)

        mock_setting.side_effect = _get
        platforms, skipped, privacy = resolve_config_publish_platforms()
        self.assertEqual(platforms, ["youtube"])
        self.assertEqual(skipped, [])
        self.assertEqual(privacy, "unlisted")


if __name__ == "__main__":
    unittest.main()
