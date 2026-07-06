"""Resolve per-channel publish targets for Upload-Post."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

UPLOAD_POST_SUPPORTED = frozenset({"youtube", "tiktok", "instagram"})

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


def resolve_config_publish_platforms() -> tuple[list[str], list[dict[str, str]], str]:
    """Resolve platforms from global config; Etapa 1 restricts to YouTube only."""
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
            if platform in UPLOAD_POST_SUPPORTED:
                platforms.append(platform)
                if platform == "youtube" and profile.get("privacy_status"):
                    youtube_privacy = str(profile["privacy_status"])
                continue
            if platform:
                reason = str(
                    profile.get("note") or "unsupported by Upload-Post"
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
        if platform in UPLOAD_POST_SUPPORTED:
            platforms.append(platform)
        elif platform:
            skipped.append(
                {
                    "platform": platform,
                    "reason": "unsupported by Upload-Post (legacy platform_targets)",
                }
            )
            logger.warning(
                "Skipping legacy platform_targets entry %r: unsupported by Upload-Post",
                platform,
            )
    return platforms, skipped, None
