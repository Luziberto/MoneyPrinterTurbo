import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import publish


@patch.dict("app.services.publish.config.app", {"publish_backend": "upload_post"})
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


class TestPublishBackendDispatch(unittest.TestCase):
    @patch.dict("app.services.publish.config.app", {"publish_backend": "zernio"})
    @patch("app.services.publish.upload_post.cross_post_video")
    @patch("app.services.publish.zernio.cross_post_video")
    @patch("app.services.publish.zernio.zernio_service")
    def test_backend_zernio_usa_wrapper_zernio(self, mock_service, mock_zernio_cross, mock_up_cross):
        mock_service.is_configured.return_value = True
        mock_service.platforms = ["tiktok"]
        mock_zernio_cross.return_value = {"success": True, "post_id": "p1"}

        with patch.object(
            publish.llm,
            "generate_social_metadata",
            return_value={"caption": "Legenda", "hashtags": ["fyp"]},
        ):
            results = publish.cross_post_videos(
                video_paths=["/fake/v.mp4"],
                subject="Assunto",
                platforms=["tiktok"],
            )

        self.assertTrue(results[0]["success"])
        mock_zernio_cross.assert_called_once()
        mock_up_cross.assert_not_called()

    @patch.dict("app.services.publish.config.app", {"publish_backend": "zernio"})
    @patch("app.services.publish.zernio.zernio_service")
    def test_backend_zernio_nao_configurado(self, mock_service):
        mock_service.is_configured.return_value = False
        results = publish.cross_post_videos(
            video_paths=["/fake/v.mp4"], subject="S", platforms=["tiktok"]
        )
        self.assertFalse(results[0]["success"])
        self.assertIn("zernio", results[0]["error"])

    @patch.dict("app.services.publish.config.app", {"publish_backend": "desconhecido"})
    @patch("app.services.publish.zernio.cross_post_video")
    @patch("app.services.publish.upload_post.cross_post_video")
    @patch("app.services.publish.upload_post.upload_post_service")
    def test_backend_default_e_upload_post(self, mock_service, mock_up_cross, mock_zernio_cross):
        mock_service.is_configured.return_value = True
        mock_service.platforms = ["tiktok"]
        mock_up_cross.return_value = {"success": True}

        with patch.object(
            publish.llm,
            "generate_social_metadata",
            return_value={"caption": "Legenda", "hashtags": []},
        ):
            publish.cross_post_videos(
                video_paths=["/fake/v.mp4"], subject="S", platforms=["tiktok"]
            )

        mock_up_cross.assert_called_once()
        mock_zernio_cross.assert_not_called()

    @patch.dict("app.services.publish.config.app", {"publish_backend": "zernio"})
    @patch("app.services.publish.zernio.zernio_service")
    def test_auto_upload_respeita_backend_zernio(self, mock_service):
        mock_service.is_configured.return_value = True
        mock_service.auto_upload = False
        results = publish.cross_post_if_auto_upload(
            video_paths=["/fake/v.mp4"],
            subject="S",
            script="",
            language="pt-BR",
        )
        self.assertEqual(results, [])
        mock_service.is_configured.assert_called_once()


if __name__ == "__main__":
    unittest.main()
