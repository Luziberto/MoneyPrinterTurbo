"""Cross-platform video publishing via Upload-Post."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from app.services import llm, upload_post

DEFAULT_FALLBACK_TITLE = "Check out this video! #shorts #viral"

# Upload-Post platform slug -> LLM metadata platform key
PLATFORM_TO_LLM = {
    "youtube": "youtube_shorts",
    "tiktok": "tiktok",
    "instagram": "instagram_reels",
}


def build_youtube_extra(
    subject: str,
    script: str,
    language: str,
    privacy_status: str,
) -> dict:
    metadata = llm.generate_social_metadata(
        video_subject=subject,
        video_script=script,
        language=language or "",
        platform="youtube_shorts",
    )
    return {
        "youtube_title": metadata.get("title", subject),
        "youtube_description": metadata.get("caption", ""),
        "tags": metadata.get("hashtags", []),
        "privacyStatus": privacy_status,
        "containsSyntheticMedia": True,
    }


def _format_caption(metadata: dict, platform: str) -> str:
    """Format caption + hashtags for TikTok/Instagram Upload-Post title field."""
    llm_key = PLATFORM_TO_LLM.get(platform, platform)
    spec = llm.SOCIAL_PLATFORMS.get(llm_key, llm.SOCIAL_PLATFORMS["tiktok"])
    caption = (metadata.get("caption") or metadata.get("title") or "").strip()
    hashtags = metadata.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = [hashtags]
    tag_text = " ".join(
        tag if str(tag).startswith("#") else f"#{tag}"
        for tag in hashtags[: spec["hashtag_count"]]
        if str(tag).strip()
    )
    parts = [part for part in (caption, tag_text) if part]
    text = " ".join(parts).strip()
    return text[: spec["caption_max"]] if text else ""


def _resolve_post_title(
    platforms: list[str],
    subject: str,
    script: str,
    language: str,
) -> str:
    social_platforms = {
        p for p in platforms if p in ("tiktok", "instagram")
    }
    if not social_platforms:
        return subject or DEFAULT_FALLBACK_TITLE

    # Prefer TikTok caption style when both are present; generate per-platform later if needed.
    primary = "tiktok" if "tiktok" in social_platforms else "instagram"
    metadata = llm.generate_social_metadata(
        video_subject=subject,
        video_script=script,
        language=language or "",
        platform=PLATFORM_TO_LLM[primary],
    )
    formatted = _format_caption(metadata, primary)
    return formatted or subject or DEFAULT_FALLBACK_TITLE


def cross_post_videos(
    video_paths: list[str],
    subject: str,
    script: str = "",
    language: str = "",
    platforms: Optional[list[str]] = None,
    youtube_privacy_status: Optional[str] = None,
) -> list[dict]:
    """
    Cross-post rendered videos to social platforms via Upload-Post.

    Returns a list of API result dicts (one per video path).
    """
    service = upload_post.upload_post_service
    if not service.is_configured():
        logger.warning("Upload-Post is not configured. Skipping cross-post.")
        return [{"success": False, "error": "Upload-Post not configured"}]

    if platforms is None:
        platforms = list(service.platforms)

    if not platforms:
        logger.warning("No publish platforms configured. Skipping cross-post.")
        return [{"success": False, "error": "No publish platforms configured"}]

    privacy = youtube_privacy_status or service.youtube_privacy_status
    logger.info(f"Cross-posting videos to {', '.join(platforms)}")

    youtube_extra = None
    if any(p.startswith("youtube") for p in platforms):
        youtube_extra = build_youtube_extra(subject, script, language, privacy)

    title = _resolve_post_title(platforms, subject, script, language)
    results: list[dict] = []
    for video_path in video_paths:
        result = upload_post.cross_post_video(
            video_path=video_path,
            title=title,
            platforms=platforms,
            youtube_extra=youtube_extra,
        )
        results.append(result)
        if result.get("success"):
            logger.info(f"Cross-posted: {video_path}")
        else:
            logger.warning(
                f"Failed to cross-post: {video_path} - {result.get('error', 'Unknown error')}"
            )
    return results


def cross_post_if_auto_upload(
    video_paths: list[str],
    subject: str,
    script: str,
    language: str,
    publish_platforms: Optional[list[str]] = None,
) -> list[dict]:
    """Run cross-post after render when global auto_upload is enabled."""
    service = upload_post.upload_post_service
    if not service.is_configured() or not service.auto_upload:
        return []
    platforms = publish_platforms if publish_platforms is not None else None
    return cross_post_videos(
        video_paths=video_paths,
        subject=subject,
        script=script,
        language=language,
        platforms=platforms,
    )
