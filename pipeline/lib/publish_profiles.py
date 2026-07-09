"""Resolve per-channel publish targets for the active publish backend."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

UPLOAD_POST_SUPPORTED = frozenset({"youtube", "tiktok", "instagram"})
ZERNIO_SUPPORTED = frozenset({"youtube", "tiktok", "instagram", "facebook"})


def publish_backend_name() -> str:
    """Active publish backend from config ("upload_post" default)."""
    try:
        from app.config import config
    except ImportError:
        return "upload_post"
    return str(config.app.get("publish_backend", "upload_post")).strip().lower()


def supported_platforms(backend: str | None = None) -> frozenset:
    backend = backend or publish_backend_name()
    return ZERNIO_SUPPORTED if backend == "zernio" else UPLOAD_POST_SUPPORTED

PLATFORM_ALIASES = {
    "youtube_shorts": "youtube",
    "instagram_reels": "instagram",
    "facebook_reels": "facebook",
    "facebook": "facebook",
    "kwai": "kwai",
    "kuaishou": "kwai",
}


def normalize_platform(name: str) -> str:
    key = (name or "").strip().lower()
    return PLATFORM_ALIASES.get(key, key)


# Etapa 1: manual publish reads config.toml (YouTube only).
# Set True after first unlisted YouTube upload is validated.
USE_CHANNEL_PUBLISH_PROFILES = False


def _resolve_zernio_config_platforms() -> tuple[list[str], list[dict[str, str]], str]:
    """Zernio reads zernio_* keys and allows every supported platform."""
    try:
        from app.services.zernio import _zernio_setting
    except ImportError:
        return ["youtube"], [], "unlisted"

    raw = _zernio_setting("zernio_platforms", ["tiktok", "youtube"]) or [
        "tiktok",
        "youtube",
    ]
    platforms: list[str] = []
    skipped: list[dict[str, str]] = []
    for item in raw:
        platform = normalize_platform(str(item))
        if platform in ZERNIO_SUPPORTED:
            if platform not in platforms:
                platforms.append(platform)
        elif platform:
            skipped.append({"platform": platform, "reason": "unsupported by Zernio"})
            logger.warning("Skipping platform %r: unsupported by Zernio", platform)
    if not platforms:
        platforms = ["youtube"]
    privacy = str(_zernio_setting("zernio_youtube_privacy_status", "unlisted"))
    return platforms, skipped, privacy


def resolve_config_publish_platforms() -> tuple[list[str], list[dict[str, str]], str]:
    """Resolve platforms from global config; Etapa 1 (Upload-Post) restricts to YouTube only."""
    if publish_backend_name() == "zernio":
        return _resolve_zernio_config_platforms()

    try:
        from app.services.upload_post import _upload_post_setting
    except ImportError:
        return ["youtube"], [], "unlisted"

    raw = _upload_post_setting("upload_post_platforms", ["youtube"]) or ["youtube"]
    platforms: list[str] = []
    for item in raw:
        if normalize_platform(str(item)) == "youtube":
            platforms.append("youtube")
            break
    if not platforms:
        platforms = ["youtube"]
    privacy = str(
        _upload_post_setting("upload_post_youtube_privacy_status", "unlisted")
    )
    return platforms, [], privacy


def resolve_publish_platforms(
    channel_config: dict[str, Any],
) -> tuple[list[str], list[dict[str, str]], str | None]:
    """
    Return (platforms_to_publish, skipped_profiles, youtube_privacy_status).

    ``youtube_privacy_status`` is taken from the enabled YouTube profile when set;
  otherwise callers should fall back to global config.
    """
    backend = publish_backend_name()
    supported = supported_platforms(backend)
    profiles = channel_config.get("publish_profiles")
    if isinstance(profiles, list) and profiles:
        platforms: list[str] = []
        skipped: list[dict[str, str]] = []
        youtube_privacy: str | None = None
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            platform = normalize_platform(str(profile.get("platform", "")))
            if not profile.get("enabled", False):
                continue
            if platform in supported:
                platforms.append(platform)
                if platform == "youtube" and profile.get("privacy_status"):
                    youtube_privacy = str(profile["privacy_status"])
                continue
            if platform:
                reason = str(
                    profile.get("note") or f"unsupported by {backend}"
                )
                skipped.append({"platform": platform, "reason": reason})
                logger.warning(
                    "Skipping publish profile %r: %s", platform, reason
                )
        return platforms, skipped, youtube_privacy

    targets = channel_config.get("platform_targets") or []
    if not isinstance(targets, list):
        targets = []
    platforms = []
    skipped = []
    for raw in targets:
        platform = normalize_platform(str(raw))
        if platform in supported:
            platforms.append(platform)
        elif platform:
            skipped.append(
                {
                    "platform": platform,
                    "reason": f"unsupported by {backend} (legacy platform_targets)",
                }
            )
            logger.warning(
                "Skipping legacy platform_targets entry %r: unsupported by %s",
                platform,
                backend,
            )
    return platforms, skipped, None
