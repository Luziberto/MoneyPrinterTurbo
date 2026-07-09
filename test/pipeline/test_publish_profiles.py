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
    UPLOAD_POST_SUPPORTED,
    ZERNIO_SUPPORTED,
    resolve_config_publish_platforms,
    resolve_publish_platforms,
    supported_platforms,
)


@patch("lib.publish_profiles.publish_backend_name", return_value="upload_post")
class TestPublishProfiles(unittest.TestCase):
    def test_publish_profiles_youtube_only(self, _backend):
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

    def test_legacy_platform_targets_fallback(self, _backend):
        platforms, skipped, privacy = resolve_publish_platforms(
            {
                "platform_targets": ["youtube", "tiktok", "facebook"],
            }
        )
        self.assertEqual(platforms, ["youtube", "tiktok"])
        self.assertIsNone(privacy)
        self.assertEqual(skipped[0]["platform"], "facebook")

    @patch("app.services.upload_post._upload_post_setting")
    def test_config_publish_platforms_youtube_only(self, mock_setting, _backend):
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


@patch("lib.publish_profiles.publish_backend_name", return_value="zernio")
class TestPublishProfilesZernio(unittest.TestCase):
    def test_supported_platforms_por_backend(self, _backend):
        self.assertEqual(supported_platforms("upload_post"), UPLOAD_POST_SUPPORTED)
        self.assertEqual(supported_platforms("zernio"), ZERNIO_SUPPORTED)
        self.assertIn("facebook", ZERNIO_SUPPORTED)
        self.assertNotIn("facebook", UPLOAD_POST_SUPPORTED)
        # sem argumento usa o backend ativo (patchado como zernio)
        self.assertEqual(supported_platforms(), ZERNIO_SUPPORTED)

    @patch("app.services.zernio._zernio_setting")
    def test_config_publish_platforms_zernio(self, mock_setting, _backend):
        def _get(key, default=None):
            values = {
                "zernio_platforms": ["tiktok", "youtube", "kwai"],
                "zernio_youtube_privacy_status": "public",
            }
            return values.get(key, default)

        mock_setting.side_effect = _get
        platforms, skipped, privacy = resolve_config_publish_platforms()
        self.assertEqual(platforms, ["tiktok", "youtube"])
        self.assertEqual(skipped[0]["platform"], "kwai")
        self.assertEqual(privacy, "public")

    def test_publish_profiles_tiktok_habilitado_no_zernio(self, _backend):
        platforms, skipped, privacy = resolve_publish_platforms(
            {
                "publish_profiles": [
                    {"platform": "youtube", "enabled": True, "privacy_status": "unlisted"},
                    {"platform": "tiktok", "enabled": True},
                    {"platform": "kwai", "enabled": True},
                ]
            }
        )
        self.assertEqual(platforms, ["youtube", "tiktok"])
        self.assertEqual(privacy, "unlisted")
        self.assertEqual(skipped[0]["platform"], "kwai")
        self.assertIn("zernio", skipped[0]["reason"])


if __name__ == "__main__":
    unittest.main()
