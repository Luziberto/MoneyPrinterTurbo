"""Assemble a VideoParams render request from a cockpit Workspace.

Port of webui/cockpit.py::sync_params_from_ui, minus the config.ui/
st.session_state indirection: every field now lives directly on the
Workspace, so this is a straight field-for-field mapping.
"""

from __future__ import annotations

from typing import Any

from app.models.schema import (
    VideoAspect,
    VideoConcatMode,
    VideoParams,
    VideoTransitionMode,
    Workspace,
)
from app.services.cockpit_state import build_channel_runtime
from app.utils.target_duration import paragraph_number_from_target_duration


def _collector_limits(workspace: Workspace, channel_runtime: dict[str, Any] | None) -> tuple[int, int]:
    if workspace.media.collector_target_clips and workspace.media.collector_min_acceptable_clips:
        return (
            int(workspace.media.collector_target_clips),
            int(workspace.media.collector_min_acceptable_clips),
        )
    collector = (channel_runtime or {}).get("collector") or {}
    target = int(collector.get("target_clips", 25) or 25)
    minimum = int(collector.get("min_acceptable_clips", 20) or 20)
    return target, minimum


def assemble_video_params(
    workspace: Workspace,
    channel_runtime: dict[str, Any] | None = None,
) -> VideoParams:
    """Build a VideoParams payload from a Workspace, ready for create_task()."""
    if channel_runtime is None and workspace.channel_slug:
        channel_runtime = build_channel_runtime(workspace.channel_slug)

    target_clips, min_clips = _collector_limits(workspace, channel_runtime)

    target_duration = str((channel_runtime or {}).get("target_duration") or "").strip()
    if target_duration:
        paragraph_number = paragraph_number_from_target_duration(target_duration)
    else:
        paragraph_number = int(workspace.script.paragraph_number or 1)

    if workspace.subtitle.subtitle_background_enabled:
        text_background_color: Any = workspace.subtitle.subtitle_background_color
    else:
        text_background_color = False

    params = VideoParams(
        video_subject=str(workspace.script.video_subject or "").strip(),
        video_script=str(workspace.script.video_script or ""),
        script_mode=workspace.script.script_mode,
        video_terms=[term.model_dump() for term in workspace.keywords.terms] or None,
        video_language=str(workspace.script.video_language or ""),
        video_aspect=VideoAspect(str(workspace.media.video_aspect)),
        video_concat_mode=VideoConcatMode(str(workspace.media.video_concat_mode)),
        video_transition_mode=(
            VideoTransitionMode(str(workspace.media.video_transition_mode))
            if workspace.media.video_transition_mode
            else None
        ),
        video_clip_duration=int(workspace.media.video_clip_duration or 3),
        match_materials_to_script=bool(workspace.script.match_materials_to_script),
        video_count=int(workspace.media.video_count or 1),
        video_source=str(workspace.media.video_source or "pexels"),
        video_materials=workspace.media.video_materials,
        video_clips=workspace.media.video_clips,
        custom_audio_file=workspace.voice.custom_audio_file,
        voice_name=str(workspace.voice.voice_name or ""),
        voice_volume=float(workspace.voice.voice_volume or 1.0),
        voice_rate=float(workspace.voice.voice_rate or 1.0),
        bgm_type=str(workspace.bgm.bgm_type or "random"),
        bgm_file=str(workspace.bgm.bgm_file or ""),
        bgm_profile=str(workspace.bgm.bgm_profile or ""),
        bgm_volume=float(workspace.bgm.bgm_volume or 0.2),
        subtitle_enabled=bool(workspace.subtitle.subtitle_enabled),
        subtitle_position=str(workspace.subtitle.subtitle_position or "bottom"),
        custom_position=float(workspace.subtitle.custom_position or 70.0),
        font_name=str(workspace.subtitle.font_name or "Roboto-Bold.ttf"),
        text_fore_color=str(workspace.subtitle.text_fore_color or "#FFFFFF"),
        text_background_color=text_background_color,
        rounded_subtitle_background=bool(workspace.subtitle.rounded_subtitle_background),
        font_size=int(workspace.subtitle.font_size or 55),
        stroke_color=str(workspace.subtitle.stroke_color or "#000000"),
        stroke_width=float(workspace.subtitle.stroke_width or 2.5),
        paragraph_number=paragraph_number,
        video_script_prompt=str(workspace.script.video_script_prompt or ""),
        custom_system_prompt=(
            str(workspace.script.custom_system_prompt or "")
            if workspace.script.use_custom_system_prompt
            else ""
        ),
        title_enabled=bool(workspace.title_overlay.title_enabled),
        title_text=str(workspace.title_overlay.title_text or ""),
        title_duration=float(workspace.title_overlay.title_duration or 3.0),
        collector_target_clips=target_clips,
        collector_min_acceptable_clips=min_clips,
        channel_slug=workspace.channel_slug,
        publish_platforms=workspace.publish.platforms or None,
    )
    return params
