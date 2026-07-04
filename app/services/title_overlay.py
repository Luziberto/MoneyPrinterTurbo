"""Minimal opening title card for channel branding."""

from __future__ import annotations

from loguru import logger
from moviepy import CompositeVideoClip, TextClip, VideoClip

from app.models.schema import VideoParams
from app.utils import utils


def apply_title_overlay(video_clip: VideoClip, params: VideoParams) -> VideoClip:
    if not getattr(params, "title_enabled", False):
        return video_clip
    title_text = (getattr(params, "title_text", "") or "").strip()
    if not title_text:
        return video_clip

    duration = float(getattr(params, "title_duration", 3.0) or 3.0)
    duration = max(0.5, min(duration, max(0.5, video_clip.duration or duration)))
    width, height = video_clip.size
    font_path = utils.resolve_font_path(params.font_name or "Roboto-Bold.ttf")
    font_size = max(28, int((getattr(params, "font_size", 55) or 55) * 1.1))

    try:
        title_clip = TextClip(
            text=title_text,
            font=font_path,
            font_size=font_size,
            color=params.text_fore_color or "#FFFFFF",
            stroke_color=params.stroke_color or "#000000",
            stroke_width=max(1.0, float(params.stroke_width or 1.5)),
            method="caption",
            size=(int(width * 0.88), None),
            text_align="center",
        ).with_duration(duration).with_position(("center", int(height * 0.12)))

        intro = video_clip.subclipped(0, duration)
        titled_intro = CompositeVideoClip(
            [intro, title_clip],
            size=(width, height),
        ).with_duration(duration)

        if (video_clip.duration or 0) > duration:
            remainder = video_clip.subclipped(duration)
            return CompositeVideoClip(
                [titled_intro.with_start(0), remainder.with_start(duration)],
                size=(width, height),
            ).with_duration(video_clip.duration)
        return titled_intro
    except Exception as exc:
        logger.warning(f"title overlay skipped: {exc}")
        return video_clip
