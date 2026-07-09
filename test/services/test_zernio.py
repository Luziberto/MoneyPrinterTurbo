import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.zernio import ZernioService


_CONFIG_BASE = {
    "zernio_enabled": True,
    "zernio_api_key": "sk_test",
    "zernio_platforms": ["tiktok", "youtube"],
    "zernio_auto_upload": True,
    "zernio_youtube_privacy_status": "unlisted",
    "zernio_tiktok_consent": True,
    "zernio_tiktok_privacy_level": "PUBLIC_TO_EVERYONE",
    "zernio_account_ids": {},
}


def _json_response(payload):
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status = MagicMock()
    return r


def _presign_response():
    return _json_response(
        {"uploadUrl": "https://bucket/upload-here", "publicUrl": "https://cdn/video.mp4"}
    )


def _post_response(post_id="post_1"):
    return _json_response({"id": post_id})


def _accounts_response():
    return _json_response(
        {
            "accounts": [
                {"platform": "tiktok", "accountId": "acc_tt"},
                {"platform": "youtube", "id": "acc_yt"},
            ]
        }
    )


def _post_calls(mock_post):
    """Return [(url, json_body), ...] for every requests.post call."""
    return [(c.args[0], c.kwargs.get("json")) for c in mock_post.call_args_list]


class TestZernioService(unittest.TestCase):

    def test_is_configured(self):
        with patch("app.services.zernio.config.app", _CONFIG_BASE):
            self.assertTrue(ZernioService().is_configured())
        with patch("app.services.zernio.config.app", {**_CONFIG_BASE, "zernio_enabled": False}):
            self.assertFalse(ZernioService().is_configured())
        with patch("app.services.zernio.config.app", {**_CONFIG_BASE, "zernio_api_key": ""}):
            self.assertFalse(ZernioService().is_configured())

    def test_account_ids_malformado_vira_dict_vazio(self):
        with patch("app.services.zernio.config.app", {**_CONFIG_BASE, "zernio_account_ids": "acc_x"}):
            svc = ZernioService()
        self.assertEqual(svc.account_ids, {})
        with patch("app.services.zernio.config.app", {**_CONFIG_BASE, "zernio_account_ids": None}):
            svc = ZernioService()
        self.assertEqual(svc.account_ids, {})

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake"))
    @patch("app.services.zernio.requests.get")
    @patch("app.services.zernio.requests.put")
    @patch("app.services.zernio.requests.post")
    def test_fluxo_presign_put_post(self, mock_post, mock_put, mock_get, _exists):
        mock_get.return_value = _accounts_response()
        mock_put.return_value = _json_response({})
        mock_post.side_effect = [_presign_response(), _post_response()]

        svc = ZernioService()
        result = svc.upload_video("/fake/v.mp4", "Legenda")

        calls = _post_calls(mock_post)
        presign_url, presign_body = calls[0]
        self.assertTrue(presign_url.endswith("/media/presign"))
        self.assertEqual(presign_body["filename"], "v.mp4")
        self.assertEqual(presign_body["contentType"], "video/mp4")
        self.assertEqual(
            mock_post.call_args_list[0].kwargs["headers"]["Authorization"],
            "Bearer sk_test",
        )

        put_call = mock_put.call_args
        self.assertEqual(put_call.args[0], "https://bucket/upload-here")
        self.assertNotIn("Authorization", put_call.kwargs.get("headers", {}))

        posts_url, body = calls[1]
        self.assertTrue(posts_url.endswith("/posts"))
        self.assertTrue(body["publishNow"])
        self.assertEqual(body["mediaItems"], [{"type": "video", "url": "https://cdn/video.mp4"}])
        self.assertEqual(body["content"], "Legenda")

        self.assertTrue(result["success"])
        self.assertEqual(result["post_id"], "post_1")
        statuses = {p["platform"]: p["status"] for p in result["platform_results"]}
        self.assertEqual(statuses, {"tiktok": "submitted", "youtube": "submitted"})

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake"))
    @patch("app.services.zernio.requests.get")
    @patch("app.services.zernio.requests.put")
    @patch("app.services.zernio.requests.post")
    def test_get_accounts_cacheado_entre_uploads(self, mock_post, mock_put, mock_get, _exists):
        mock_get.return_value = _accounts_response()
        mock_put.return_value = _json_response({})
        mock_post.side_effect = [
            _presign_response(), _post_response("p1"),
            _presign_response(), _post_response("p2"),
        ]

        svc = ZernioService()
        svc.upload_video("/fake/v1.mp4", "T1")
        svc.upload_video("/fake/v2.mp4", "T2")

        self.assertEqual(mock_get.call_count, 1)

    @patch("app.services.zernio.config.app", {
        **_CONFIG_BASE,
        "zernio_account_ids": {"tiktok": "acc_cfg_tt", "youtube": "acc_cfg_yt"},
    })
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake"))
    @patch("app.services.zernio.requests.get")
    @patch("app.services.zernio.requests.put")
    @patch("app.services.zernio.requests.post")
    def test_account_ids_explicito_pula_get(self, mock_post, mock_put, mock_get, _exists):
        mock_put.return_value = _json_response({})
        mock_post.side_effect = [_presign_response(), _post_response()]

        svc = ZernioService()
        result = svc.upload_video("/fake/v.mp4", "T")

        mock_get.assert_not_called()
        _, body = _post_calls(mock_post)[1]
        account_ids = {p["platform"]: p["accountId"] for p in body["platforms"]}
        self.assertEqual(account_ids, {"tiktok": "acc_cfg_tt", "youtube": "acc_cfg_yt"})
        self.assertTrue(result["success"])

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake"))
    @patch("app.services.zernio.requests.get")
    @patch("app.services.zernio.requests.put")
    @patch("app.services.zernio.requests.post")
    def test_youtube_platform_specific_data(self, mock_post, mock_put, mock_get, _exists):
        mock_get.return_value = _accounts_response()
        mock_put.return_value = _json_response({})
        mock_post.side_effect = [_presign_response(), _post_response()]

        svc = ZernioService()
        svc.upload_video(
            "/fake/v.mp4",
            "T",
            platforms=["youtube"],
            youtube_extra={
                "youtube_title": "X" * 150,
                "youtube_description": "Desc",
                "tags": ["japao"],
                "privacyStatus": "public",
                "containsSyntheticMedia": False,
            },
        )

        _, body = _post_calls(mock_post)[1]
        entry = body["platforms"][0]
        self.assertEqual(entry["platform"], "youtube")
        data = entry["platformSpecificData"]
        self.assertEqual(len(data["title"]), 100)
        self.assertEqual(data["visibility"], "public")
        self.assertIs(data["containsSyntheticMedia"], True)
        self.assertIs(data["madeForKids"], False)

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake"))
    @patch("app.services.zernio.requests.get")
    @patch("app.services.zernio.requests.put")
    @patch("app.services.zernio.requests.post")
    def test_tiktok_consent_flags_presentes(self, mock_post, mock_put, mock_get, _exists):
        mock_get.return_value = _accounts_response()
        mock_put.return_value = _json_response({})
        mock_post.side_effect = [_presign_response(), _post_response()]

        svc = ZernioService()
        svc.upload_video("/fake/v.mp4", "T", platforms=["tiktok"])

        _, body = _post_calls(mock_post)[1]
        data = body["platforms"][0]["platformSpecificData"]
        self.assertIs(data["content_preview_confirmed"], True)
        self.assertIs(data["express_consent_given"], True)
        self.assertEqual(data["privacy_level"], "PUBLIC_TO_EVERYONE")

    @patch("app.services.zernio.config.app", {**_CONFIG_BASE, "zernio_tiktok_consent": False})
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake"))
    @patch("app.services.zernio.requests.get")
    @patch("app.services.zernio.requests.put")
    @patch("app.services.zernio.requests.post")
    def test_tiktok_pulado_sem_consent_youtube_segue(self, mock_post, mock_put, mock_get, _exists):
        mock_get.return_value = _accounts_response()
        mock_put.return_value = _json_response({})
        mock_post.side_effect = [_presign_response(), _post_response()]

        svc = ZernioService()
        result = svc.upload_video("/fake/v.mp4", "T", platforms=["tiktok", "youtube"])

        _, body = _post_calls(mock_post)[1]
        self.assertEqual([p["platform"] for p in body["platforms"]], ["youtube"])
        self.assertTrue(result["success"])
        skipped = [p for p in result["platform_results"] if p["status"] == "skipped"]
        self.assertEqual(skipped[0]["platform"], "tiktok")
        self.assertIn("zernio_tiktok_consent", skipped[0]["error"])

    @patch("app.services.zernio.config.app", {**_CONFIG_BASE, "zernio_tiktok_consent": False})
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("app.services.zernio.requests.post")
    def test_sem_plataformas_publicaveis_falha(self, mock_post, _exists):
        svc = ZernioService()
        result = svc.upload_video("/fake/v.mp4", "T", platforms=["tiktok"])

        mock_post.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("No publishable platforms", result["error"])

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    def test_build_content_youtube_only_usa_description(self):
        svc = ZernioService()
        content = svc._build_content(
            ["youtube"],
            "Assunto",
            {"youtube_description": "Descrição longa", "tags": ["japao", "#shorts"]},
        )
        self.assertIn("Descrição longa", content)
        self.assertIn("#japao", content)
        self.assertIn("#shorts", content)

        misto = svc._build_content(
            ["tiktok", "youtube"],
            "Legenda TikTok #fyp",
            {"youtube_description": "Descrição"},
        )
        self.assertEqual(misto, "Legenda TikTok #fyp")

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    def test_build_content_cap_2200(self):
        svc = ZernioService()
        content = svc._build_content(["tiktok"], "x" * 3000, None)
        self.assertEqual(len(content), 2200)

    @patch("app.services.zernio.config.app", _CONFIG_BASE)
    @patch("app.services.zernio.os.path.exists", return_value=False)
    def test_arquivo_ausente_falha(self, _exists):
        svc = ZernioService()
        result = svc.upload_video("/fake/missing.mp4", "T")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    @patch("app.services.zernio.config.app", {
        **_CONFIG_BASE,
        "zernio_account_ids": {"tiktok": "acc_tt", "youtube": "acc_yt"},
    })
    @patch("app.services.zernio.os.path.exists", return_value=True)
    @patch("app.services.zernio.requests.post")
    def test_presign_falha_retorna_erro(self, mock_post, _exists):
        mock_post.side_effect = requests.exceptions.RequestException("presign boom")

        svc = ZernioService()
        result = svc.upload_video("/fake/v.mp4", "T")

        self.assertFalse(result["success"])
        self.assertIn("presign boom", result["error"])


if __name__ == "__main__":
    unittest.main()
