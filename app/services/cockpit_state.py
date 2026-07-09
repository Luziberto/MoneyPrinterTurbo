"""Pure-logic cockpit helpers, ported from webui/cockpit.py's session_state
functions to operate on a Workspace object instead. Shared by
app/controllers/v1/cockpit.py and app/controllers/v1/channels.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.models.schema import Workspace
from app.utils import utils
from app.utils.target_duration import paragraph_number_from_target_duration

ROOT_DIR = Path(__file__).resolve().parents[2]
PIPELINE_DIR = ROOT_DIR / "pipeline"

STEP_IDS = (
    "script",
    "collector",
    "preview",
    "render",
    "result",
    "publish",
)
PIPELINE_STEP_COUNT = len(STEP_IDS)

# Flat runtime-key -> (workspace group, workspace field) mapping. Mirrors
# webui/cockpit.py's RUNTIME_SESSION_KEYS + RUNTIME_UI_KEYS.
RUNTIME_FIELD_MAP: dict[str, tuple[str, str]] = {
    "video_subject": ("script", "video_subject"),
    "paragraph_number_input": ("script", "paragraph_number"),
    "match_materials_to_script": ("script", "match_materials_to_script"),
    "video_script_prompt": ("script", "video_script_prompt"),
    "script_mode": ("script", "script_mode"),
    "video_language": ("script", "video_language"),
    "title_enabled": ("title_overlay", "title_enabled"),
    "title_text": ("title_overlay", "title_text"),
    "title_duration": ("title_overlay", "title_duration"),
    "video_source": ("media", "video_source"),
    "video_aspect": ("media", "video_aspect"),
    "video_concat_mode": ("media", "video_concat_mode"),
    "video_transition_mode": ("media", "video_transition_mode"),
    "video_clip_duration": ("media", "video_clip_duration"),
    "video_count": ("media", "video_count"),
    "bgm_type": ("bgm", "bgm_type"),
    "bgm_profile": ("bgm", "bgm_profile"),
    "bgm_file": ("bgm", "bgm_file"),
    "bgm_volume": ("bgm", "bgm_volume"),
    "voice_name": ("voice", "voice_name"),
    "voice_volume": ("voice", "voice_volume"),
    "voice_rate": ("voice", "voice_rate"),
    "tts_server": ("voice", "tts_server"),
    "font_name": ("subtitle", "font_name"),
    "font_size": ("subtitle", "font_size"),
    "subtitle_position": ("subtitle", "subtitle_position"),
    "text_fore_color": ("subtitle", "text_fore_color"),
    "stroke_color": ("subtitle", "stroke_color"),
    "stroke_width": ("subtitle", "stroke_width"),
    "subtitle_enabled": ("subtitle", "subtitle_enabled"),
    "subtitle_background_enabled": ("subtitle", "subtitle_background_enabled"),
    "subtitle_background_color": ("subtitle", "subtitle_background_color"),
    "rounded_subtitle_background": ("subtitle", "rounded_subtitle_background"),
    "custom_position": ("subtitle", "custom_position"),
}


def ensure_pipeline_path() -> None:
    pipeline_path = str(PIPELINE_DIR)
    if pipeline_path not in sys.path:
        sys.path.insert(0, pipeline_path)


def _normalize_runtime_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, bool):
        return bool(value)
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return value
    return str(value)


def build_channel_runtime(slug: str) -> dict[str, Any]:
    """Flat runtime snapshot from channel.json, for form/override comparison.

    Port of webui/cockpit.py::build_runtime_config.
    """
    ensure_pipeline_path()
    from lib.channel import load_channel

    channel = load_channel(slug)
    transition = channel.get("video_transition_mode")
    if transition is not None and hasattr(transition, "value"):
        transition = transition.value

    target_duration = str(channel.get("target_duration", "") or "")
    if target_duration:
        paragraph_number = paragraph_number_from_target_duration(target_duration)
    else:
        paragraph_number = int(channel.get("paragraph_number", 1) or 1)

    try:
        videos_per_day = max(1, int(channel.get("videos_per_day", 1) or 1))
    except (TypeError, ValueError):
        videos_per_day = 1

    from lib.topic_store import TopicStore

    videos_generated_today = TopicStore().count_generated_today(slug)

    return {
        "slug": slug,
        "name": str(channel.get("name", slug) or slug),
        "video_subject": str(channel.get("niche", "") or "").strip(),
        "paragraph_number_input": paragraph_number,
        "match_materials_to_script": bool(channel.get("match_materials_to_script", False)),
        "video_script_prompt": str(channel.get("video_script_prompt", "") or "").strip(),
        "title_enabled": bool(channel.get("title_enabled", False)),
        "title_text": str(
            channel.get("title_text", "") or channel.get("name", "") or ""
        ).strip(),
        "title_duration": float(channel.get("title_duration", 3.0) or 3.0),
        "video_source": str(channel.get("video_source", "collector") or "collector"),
        "bgm_type": str(channel.get("bgm_type", "random") or "random"),
        "bgm_profile": str(channel.get("bgm_profile", "") or ""),
        "bgm_file": "",
        "bgm_volume": float(channel.get("bgm_volume", 0.2) or 0.2),
        "font_name": str(channel.get("font_name", "Roboto-Bold.ttf") or "Roboto-Bold.ttf"),
        "font_size": int(channel.get("font_size", 55) or 55),
        "subtitle_position": str(channel.get("subtitle_position", "bottom") or "bottom"),
        "text_fore_color": str(channel.get("text_fore_color", "#FFFFFF") or "#FFFFFF"),
        "voice_name": str(channel.get("voice_name", "") or "").strip(),
        "voice_volume": float(channel.get("voice_volume", 1.0) or 1.0),
        "voice_rate": float(channel.get("voice_rate", 1.0) or 1.0),
        "tts_server": "azure-tts-v1",
        "video_aspect": str(channel.get("video_aspect", "") or "").strip() or "9:16",
        "video_language": str(channel.get("video_language", "") or ""),
        "subtitle_enabled": bool(channel.get("subtitle_enabled", True)),
        "stroke_color": str(channel.get("stroke_color", "#000000") or "#000000"),
        "stroke_width": float(channel.get("stroke_width", 2.5) or 2.5),
        "subtitle_background_enabled": bool(
            channel.get("subtitle_background_enabled", True)
        ),
        "subtitle_background_color": str(
            channel.get("subtitle_background_color", "#000000") or "#000000"
        ),
        "rounded_subtitle_background": bool(
            channel.get("rounded_subtitle_background", False)
        ),
        "custom_position": float(channel.get("custom_position", 70.0) or 70.0),
        "video_concat_mode": str(channel.get("video_concat_mode", "random") or "random"),
        "video_transition_mode": transition,
        "video_clip_duration": int(channel.get("video_clip_duration", 3) or 3),
        "video_count": int(channel.get("video_count", 1) or 1),
        "target_duration": str(channel.get("target_duration", "") or ""),
        "target_words": str(channel.get("target_words", "") or ""),
        "videos_per_day": videos_per_day,
        "videos_generated_today": videos_generated_today,
        "mode": str(channel.get("mode", "faceless") or "faceless"),
        "collector": dict(channel.get("collector") or {}),
    }


def workspace_seed_from_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    """Map a flat channel runtime dict into a Workspace-shaped seed dict."""
    seed: dict[str, dict[str, Any]] = {
        "script": {},
        "media": {},
        "voice": {},
        "bgm": {},
        "subtitle": {},
        "title_overlay": {},
    }
    for runtime_key, (group, field) in RUNTIME_FIELD_MAP.items():
        if runtime_key in runtime and runtime[runtime_key] is not None:
            seed[group][field] = runtime[runtime_key]
    collector = runtime.get("collector") or {}
    if collector:
        seed["media"]["collector_target_clips"] = collector.get("target_clips")
        seed["media"]["collector_min_acceptable_clips"] = collector.get("min_acceptable_clips")
    return seed


def flatten_workspace(workspace: Workspace) -> dict[str, Any]:
    """Inverse of workspace_seed_from_runtime: flatten Workspace fields back
    into the same flat key space as build_channel_runtime, for override diffing.
    """
    flat: dict[str, Any] = {}
    groups = {
        "script": workspace.script,
        "media": workspace.media,
        "voice": workspace.voice,
        "bgm": workspace.bgm,
        "subtitle": workspace.subtitle,
        "title_overlay": workspace.title_overlay,
    }
    for runtime_key, (group, field) in RUNTIME_FIELD_MAP.items():
        flat[runtime_key] = getattr(groups[group], field)
    return flat


def detect_overrides(runtime: dict[str, Any], workspace: Workspace) -> list[str]:
    """Return the flat keys where the workspace diverges from the channel baseline.

    Port of webui/cockpit.py::detect_overrides.
    """
    form = flatten_workspace(workspace)
    overrides: list[str] = []
    for key in RUNTIME_FIELD_MAP:
        if key not in runtime:
            continue
        runtime_val = _normalize_runtime_value(runtime.get(key))
        form_val = _normalize_runtime_value(form.get(key))
        if form_val is None and runtime_val in (None, "", 0, False):
            continue
        if form_val != runtime_val:
            overrides.append(key)
    return overrides


def compute_pipeline_step_states(workspace: Workspace) -> list[str]:
    """Return per-step status: done, active, pending.

    Port of webui/cockpit.py::compute_pipeline_step_states.
    """
    active = max(0, min(workspace.active_step, PIPELINE_STEP_COUNT - 1))

    done = [False] * PIPELINE_STEP_COUNT
    done[0] = bool(str(workspace.script.video_script or "").strip())

    if workspace.media.video_source == "collector":
        job = workspace.media.last_collector_job or {}
        done[1] = (
            job.get("status") == "ready"
            or int(job.get("selected_clips_count") or 0) > 0
        )
    else:
        done[1] = done[0]

    done[2] = bool(workspace.preview.ready)

    last_task = workspace.render.last_render_task_id
    if last_task:
        task_dir = Path(utils.task_dir()) / str(last_task)
        if (task_dir / "final-1.mp4").is_file():
            done[3] = True
            done[4] = True

    if workspace.publish.done or workspace.publish.mode == "skip":
        done[5] = True

    states: list[str] = []
    for index in range(PIPELINE_STEP_COUNT):
        if index == active:
            states.append("active")
        elif done[index]:
            states.append("done")
        else:
            states.append("pending")
    return states
