import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import publish


class TestPublishService(unittest.TestCase):
    def test_build_youtube_extra_uses_llm_metadata(self):
        with patch.object(
            publish.llm,
            "generate_social_metadata",
            return_value={
                "title": "YT Title",
                "caption": "YT Description",
                "hashtags": ["japao", "shorts"],
            },
        ) as mock_llm:
            extra = publish.build_youtube_extra(
                subject="Assunto",
                script="Roteiro",
                language="pt-BR",
                privacy_status="unlisted",
            )

        mock_llm.assert_called_once_with(
            video_subject="Assunto",
            video_script="Roteiro",
            language="pt-BR",
            platform="youtube_shorts",
        )
        self.assertEqual(extra["youtube_title"], "YT Title")
        self.assertEqual(extra["youtube_description"], "YT Description")
        self.assertEqual(extra["tags"], ["japao", "shorts"])
        self.assertEqual(extra["privacyStatus"], "unlisted")
        self.assertTrue(extra["containsSyntheticMedia"])

    def test_format_caption_includes_hashtags(self):
        metadata = {
            "caption": "Curiosidade do Japão",
            "hashtags": ["japao", "shorts"],
        }
        text = publish._format_caption(metadata, "tiktok")
        self.assertIn("Curiosidade do Japão", text)
        self.assertIn("#japao", text)
        self.assertIn("#shorts", text)

    @patch("app.services.publish.upload_post.cross_post_video")
    @patch("app.services.publish.upload_post.upload_post_service")
    def test_cross_post_videos_youtube_only(self, mock_service, mock_cross):
        mock_service.is_configured.return_value = True
        mock_service.platforms = ["youtube"]
        mock_service.youtube_privacy_status = "unlisted"
        mock_cross.return_value = {"success": True, "request_id": "abc"}

        with patch.object(
            publish.llm,
            "generate_social_metadata",
            return_value={
                "title": "T",
                "caption": "D",
                "hashtags": ["shorts"],
            },
        ):
            results = publish.cross_post_videos(
                video_paths=["/fake/v.mp4"],
                subject="Assunto",
                script="Script",
                language="pt-BR",
                platforms=["youtube"],
            )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        mock_cross.assert_called_once()
        kwargs = mock_cross.call_args[1]
        self.assertEqual(kwargs["platforms"], ["youtube"])
        self.assertIn("youtube_title", kwargs["youtube_extra"])

    @patch("app.services.publish.upload_post.cross_post_video")
    @patch("app.services.publish.upload_post.upload_post_service")
    def test_cross_post_videos_tiktok_uses_formatted_caption(self, mock_service, mock_cross):
        mock_service.is_configured.return_value = True
        mock_service.platforms = ["tiktok"]
        mock_cross.return_value = {"success": True}

        with patch.object(
            publish.llm,
            "generate_social_metadata",
            return_value={
                "caption": "Legenda TikTok",
                "hashtags": ["fyp"],
            },
        ):
            publish.cross_post_videos(
                video_paths=["/fake/v.mp4"],
                subject="Assunto",
                script="Script",
                platforms=["tiktok"],
            )

        title = mock_cross.call_args[1]["title"]
        self.assertIn("Legenda TikTok", title)
        self.assertIn("#fyp", title)
        self.assertIsNone(mock_cross.call_args[1]["youtube_extra"])

    @patch("app.services.publish.upload_post.upload_post_service")
    def test_cross_post_if_auto_upload_disabled(self, mock_service):
        mock_service.is_configured.return_value = True
        mock_service.auto_upload = False
        results = publish.cross_post_if_auto_upload(
            video_paths=["/fake/v.mp4"],
            subject="S",
            script="",
            language="pt-BR",
        )
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
