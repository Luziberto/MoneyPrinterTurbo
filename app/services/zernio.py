"""
Zernio API integration for cross-posting videos to TikTok, Instagram and YouTube Shorts.

Flow: presign upload URL -> PUT the video file -> create the post referencing
the returned public URL. Account ids are auto-discovered via GET /accounts
unless pinned in config (zernio_account_ids).

Docs: https://docs.zernio.com
"""
import os
from typing import Optional

import requests
from loguru import logger
from app.config import config

CAPTION_MAX = 2200
YOUTUBE_TITLE_MAX = 100


def _zernio_setting(key: str, default=None):
    """Read Zernio settings from [app] (no legacy [ui] fallback)."""
    return config.app.get(key, default)


class ZernioService:
    API_BASE = "https://zernio.com/api/v1"

    def __init__(self):
        self.api_key = _zernio_setting("zernio_api_key", "")
        self.enabled = bool(_zernio_setting("zernio_enabled", False))
        self.platforms = _zernio_setting("zernio_platforms", ["tiktok", "youtube"]) or [
            "tiktok",
            "youtube",
        ]
        self.auto_upload = bool(_zernio_setting("zernio_auto_upload", False))
        self.youtube_privacy_status = _zernio_setting(
            "zernio_youtube_privacy_status", "unlisted"
        )
        self.tiktok_consent = bool(_zernio_setting("zernio_tiktok_consent", False))
        self.tiktok_privacy_level = _zernio_setting(
            "zernio_tiktok_privacy_level", "PUBLIC_TO_EVERYONE"
        )
        account_ids = _zernio_setting("zernio_account_ids", {})
        if not isinstance(account_ids, dict):
            if account_ids:
                logger.warning(
                    "zernio_account_ids must be a table (e.g. { tiktok = \"acc_...\" }); ignoring."
                )
            account_ids = {}
        self.account_ids = {
            str(k).strip().lower(): str(v) for k, v in account_ids.items() if v
        }
        self._accounts_cache: Optional[dict] = None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.enabled)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _fetch_accounts(self) -> dict:
        """Map platform -> accountId from GET /accounts (cached per process)."""
        if self._accounts_cache is None:
            response = requests.get(
                f"{self.API_BASE}/accounts", headers=self._headers(), timeout=30
            )
            response.raise_for_status()
            payload = response.json() or {}
            accounts = payload.get("accounts") if isinstance(payload, dict) else payload
            mapping: dict = {}
            for account in accounts or []:
                if not isinstance(account, dict):
                    continue
                platform = str(account.get("platform", "")).strip().lower()
                account_id = (
                    account.get("accountId") or account.get("id") or account.get("_id")
                )
                if platform and account_id and platform not in mapping:
                    mapping[platform] = str(account_id)
            self._accounts_cache = mapping
        return self._accounts_cache

    def _resolve_account_id(self, platform: str) -> Optional[str]:
        explicit = self.account_ids.get(platform)
        if explicit:
            return explicit
        try:
            return self._fetch_accounts().get(platform)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list Zernio accounts: {str(e)}")
            return None

    def _build_content(
        self, platforms: list, title: str, youtube_extra: Optional[dict]
    ) -> str:
        """
        Post-level content doubles as the YouTube description on Zernio.
        YouTube-only posts use description + hashtags; mixed posts keep the
        TikTok-style caption already resolved by the publish layer.
        """
        non_youtube = [p for p in platforms if not str(p).startswith("youtube")]
        if not non_youtube and youtube_extra:
            description = str(youtube_extra.get("youtube_description") or "").strip()
            tags = youtube_extra.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            tag_text = " ".join(
                tag if str(tag).startswith("#") else f"#{tag}"
                for tag in tags
                if str(tag).strip()
            )
            content = "\n\n".join(part for part in (description, tag_text) if part)
            if content.strip():
                return content[:CAPTION_MAX]
        return (title or "")[:CAPTION_MAX]

    def _build_platform_entries(
        self, platforms: list, youtube_extra: Optional[dict]
    ) -> tuple[list, list]:
        """Return (platform entries for POST /posts, skipped platform results)."""
        entries: list = []
        skipped: list = []
        for raw in platforms:
            platform = str(raw).strip().lower()
            zernio_platform = "youtube" if platform.startswith("youtube") else platform

            if zernio_platform == "tiktok" and not self.tiktok_consent:
                reason = (
                    "TikTok consent not given: set zernio_tiktok_consent = true "
                    "in config.toml"
                )
                logger.warning(f"Skipping TikTok on Zernio: {reason}")
                skipped.append(
                    {"platform": zernio_platform, "status": "skipped", "error": reason}
                )
                continue

            account_id = self._resolve_account_id(zernio_platform)
            if not account_id:
                reason = (
                    f"No Zernio account connected for '{zernio_platform}' "
                    "(check GET /accounts or zernio_account_ids)"
                )
                logger.warning(f"Skipping {zernio_platform} on Zernio: {reason}")
                skipped.append(
                    {"platform": zernio_platform, "status": "skipped", "error": reason}
                )
                continue

            entry: dict = {"platform": zernio_platform, "accountId": account_id}
            if zernio_platform == "youtube":
                data = {
                    "visibility": str(
                        (youtube_extra or {}).get("privacyStatus")
                        or self.youtube_privacy_status
                    ),
                    "madeForKids": False,
                    "containsSyntheticMedia": True,
                }
                yt_title = (youtube_extra or {}).get("youtube_title")
                if yt_title:
                    data["title"] = str(yt_title)[:YOUTUBE_TITLE_MAX]
                entry["platformSpecificData"] = data
            elif zernio_platform == "tiktok":
                entry["platformSpecificData"] = {
                    "privacy_level": self.tiktok_privacy_level,
                    "content_preview_confirmed": True,
                    "express_consent_given": True,
                }
            entries.append(entry)
        return entries, skipped

    def _upload_media(self, video_path: str) -> str:
        """Presign, PUT the file (streamed) and return the public media URL."""
        presign = requests.post(
            f"{self.API_BASE}/media/presign",
            headers=self._headers(),
            json={
                "filename": os.path.basename(video_path),
                "contentType": "video/mp4",
            },
            timeout=30,
        )
        presign.raise_for_status()
        info = presign.json() or {}
        upload_url = info.get("uploadUrl")
        public_url = info.get("publicUrl")
        if not upload_url or not public_url:
            raise requests.exceptions.RequestException(
                f"Unexpected Zernio presign response: {info}"
            )
        with open(video_path, "rb") as video_file:
            put_response = requests.put(
                upload_url,
                data=video_file,
                headers={"Content-Type": "video/mp4"},
                timeout=600,
            )
        put_response.raise_for_status()
        return public_url

    def upload_video(
        self,
        video_path: str,
        title: str,
        platforms: Optional[list] = None,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        youtube_extra: Optional[dict] = None,
    ) -> dict:
        # privacy_level kept for signature parity with UploadPostService;
        # TikTok privacy comes from zernio_tiktok_privacy_level.
        if not self.is_configured():
            logger.warning("Zernio is not configured. Skipping cross-post.")
            return {"success": False, "error": "Zernio not configured"}

        if platforms is None:
            platforms = self.platforms

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return {"success": False, "error": f"Video file not found: {video_path}"}

        entries, platform_results = self._build_platform_entries(
            platforms, youtube_extra
        )
        if not entries:
            return {
                "success": False,
                "error": "No publishable platforms for Zernio",
                "platform_results": platform_results,
            }

        targets = [entry["platform"] for entry in entries]
        logger.info(f"Cross-posting video to {', '.join(targets)} via Zernio...")

        try:
            public_url = self._upload_media(video_path)
            body = {
                "content": self._build_content(platforms, title, youtube_extra),
                "publishNow": True,
                "mediaItems": [{"type": "video", "url": public_url}],
                "platforms": entries,
            }
            response = requests.post(
                f"{self.API_BASE}/posts",
                headers=self._headers(),
                json=body,
                timeout=300,
            )
            response.raise_for_status()
            result = response.json() or {}

            post_id = (
                result.get("id")
                or result.get("postId")
                or (result.get("post") or {}).get("id")
            )
            # Delivery is async on Zernio's side; a 2xx means the post was
            # accepted for every entry we sent.
            for entry in entries:
                platform_results.append(
                    {"platform": entry["platform"], "status": "submitted"}
                )
            logger.info(f"✅ Video cross-posted via Zernio! Post ID: {post_id}")
            return {
                "success": True,
                "post_id": post_id,
                "platform_results": platform_results,
                "raw": result,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cross-post video via Zernio: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "platform_results": platform_results,
            }


# Singleton instance
zernio_service = ZernioService()


def cross_post_video(
    video_path: str,
    title: str,
    platforms: Optional[list] = None,
    youtube_extra: Optional[dict] = None,
) -> dict:
    return zernio_service.upload_video(video_path, title, platforms, youtube_extra=youtube_extra)
