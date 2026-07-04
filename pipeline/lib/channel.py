"""Load channel configuration from channel.json + script_prompt.md."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNELS_DIR = PIPELINE_DIR / "channels"
DATA_DIR = PIPELINE_DIR / "data"
ROOT_DIR = PIPELINE_DIR.parent

SCRIPT_PROMPT_FILENAME = "script_prompt.md"
CHANNEL_JSON_FILENAME = "channel.json"

CHANNEL_DEFAULTS: dict[str, Any] = {
    "video_language": "pt-BR",
    "voice_name": "",
    "voice_volume": 1.0,
    "voice_rate": 1.0,
    "videos_per_day": 1,
    "schedule": [],
    "platform_targets": [],
    "target_duration": "60-90",
    "target_words": "120-180",
    "paragraph_number": 3,
    "video_source": "pexels",
    "video_aspect": "9:16",
    "video_concat_mode": "random",
    "video_transition_mode": None,
    "video_clip_duration": 3,
    "video_count": 1,
    "font_name": "Roboto-Bold.ttf",
    "font_size": 55,
    "subtitle_enabled": True,
    "subtitle_position": "bottom",
    "custom_position": 70.0,
    "text_fore_color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": 2.5,
    "subtitle_background_enabled": True,
    "subtitle_background_color": "#000000",
    "rounded_subtitle_background": False,
    "bgm_type": "random",
    "bgm_profile": "",
    "bgm_volume": 0.2,
    "n_threads": 2,
    "category_overrides": {},
    "music_profile_overrides": {},
    "topic_distribution": {},
    "match_materials_to_script": False,
    "mode": "faceless",
}


def load_settings() -> dict[str, Any]:
    path = PIPELINE_DIR / "settings.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def channel_dir(channel: str) -> Path:
    return CHANNELS_DIR / channel


def list_channels() -> list[str]:
    if not CHANNELS_DIR.is_dir():
        return []
    channels: list[str] = []
    for path in sorted(CHANNELS_DIR.iterdir()):
        if path.is_dir() and (path / CHANNEL_JSON_FILENAME).is_file():
            channels.append(path.name)
    return channels


def _apply_niche_to_prompt(prompt: str, niche: str) -> str:
    prompt = (prompt or "").strip()
    niche = (niche or "").strip()
    if not niche:
        return prompt
    if "{niche}" in prompt:
        return prompt.replace("{niche}", niche)
    if prompt:
        return f"{prompt}\n\nNicho: {niche}."
    return f"Nicho: {niche}."


def _normalize_channel_collections(config: dict[str, Any]) -> None:
    for key in ("category_overrides", "music_profile_overrides", "topic_distribution"):
        if not isinstance(config.get(key), dict):
            config[key] = {}
    for key in ("schedule", "platform_targets"):
        if not isinstance(config.get(key), list):
            config[key] = []


def load_channel(slug: str) -> dict[str, Any]:
    """
    Load unified channel config from channel.json + script_prompt.md.

    Returns a dict ready for build_video_payload(), including
    video_script_prompt with {niche} substitution applied.
    """
    base = channel_dir(slug)
    json_path = base / CHANNEL_JSON_FILENAME
    if not json_path.is_file():
        raise FileNotFoundError(f"Channel config not found: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        raw_config: dict[str, Any] = json.load(f)

    config = deepcopy(CHANNEL_DEFAULTS)
    config.update(raw_config)
    _normalize_channel_collections(config)

    try:
        from app.services.modes import apply_mode_defaults

        config = apply_mode_defaults(config)
    except ImportError:
        pass

    prompt_path = base / SCRIPT_PROMPT_FILENAME
    raw_prompt = ""
    if prompt_path.is_file():
        raw_prompt = prompt_path.read_text(encoding="utf-8")

    niche = str(config.get("niche", ""))
    config["video_script_prompt"] = _apply_niche_to_prompt(raw_prompt, niche)
    config["slug"] = str(config.get("slug") or slug)
    config["name"] = config.get("name", slug)

    return config


def default_db_path() -> Path:
    return DATA_DIR / "pipeline.db"
