#!/usr/bin/env python3
"""One-shot migration: profile+preset → channel.json + script_prompt.md; topics.json → SQLite."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from lib.channel import (  # noqa: E402
    CHANNEL_JSON_FILENAME,
    CHANNELS_DIR,
    CHANNEL_DEFAULTS,
    SCRIPT_PROMPT_FILENAME,
    channel_dir,
)
from lib.topic_store import TopicStore  # noqa: E402

PRESETS_DIR = _PIPELINE_DIR / "presets"
DEFAULT_PRESET = "facebook_60_90"

PROFILE_KEYS = (
    "slug",
    "name",
    "niche",
    "video_language",
    "voice_name",
    "font_name",
    "videos_per_day",
    "schedule",
)

PRESET_KEYS = (
    "platform_targets",
    "target_duration",
    "target_words",
    "paragraph_number",
    "video_source",
    "video_aspect",
    "video_clip_duration",
    "video_count",
    "font_size",
    "subtitle_position",
    "text_fore_color",
    "stroke_color",
    "stroke_width",
    "subtitle_background_enabled",
    "subtitle_background_color",
    "rounded_subtitle_background",
)


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def build_channel_json(profile: dict, preset: dict, slug: str) -> dict:
    data: dict = deepcopy(CHANNEL_DEFAULTS)
    data["slug"] = slug
    for key in PROFILE_KEYS:
        if key in profile:
            data[key] = profile[key]
    for key in PRESET_KEYS:
        if key in preset:
            data[key] = preset[key]
    data.setdefault("slug", slug)
    return data


def migrate_channel(
    channel: str,
    preset_slug: str,
    *,
    dry_run: bool = False,
    remove_legacy: bool = False,
) -> None:
    base = channel_dir(channel)
    profile_path = base / "profile.toml"
    preset_path = PRESETS_DIR / f"{preset_slug}.toml"
    topics_path = base / "topics.json"
    json_out = base / CHANNEL_JSON_FILENAME
    prompt_out = base / SCRIPT_PROMPT_FILENAME

    if not profile_path.is_file():
        print(f"Skip channel files: {profile_path} not found (may already be migrated)")
        profile = {}
    else:
        profile = _load_toml(profile_path)

    if not preset_path.is_file() and not json_out.is_file():
        raise FileNotFoundError(f"Preset not found: {preset_path}")

    preset = _load_toml(preset_path) if preset_path.is_file() else {}
    channel_data = build_channel_json(profile, preset, channel)
    raw_prompt = str(preset.get("video_script_prompt", "")).strip()

    if json_out.is_file() and not profile_path.is_file():
        print(f"{json_out} already exists — skipping channel file generation")
    elif dry_run:
        print(f"Would write {json_out}")
        print(f"Would write {prompt_out} ({len(raw_prompt)} chars)")
    else:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(channel_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        prompt_out.write_text(raw_prompt + "\n", encoding="utf-8")
        print(f"Wrote {json_out}")
        print(f"Wrote {prompt_out}")

    if topics_path.is_file():
        store = TopicStore()
        if dry_run:
            with open(topics_path, encoding="utf-8") as f:
                items = json.load(f)
            print(f"Would import {len(items)} topics from {topics_path} → {store.db_path}")
        else:
            count = store.import_from_json_file(channel, topics_path, replace=True)
            print(f"Imported {count} topics into {store.db_path}")
    else:
        print(f"No {topics_path} — skipping topic import")

    if remove_legacy and not dry_run:
        for path in (profile_path, topics_path):
            if path.is_file():
                path.unlink()
                print(f"Removed {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate channel layout to channel.json + script_prompt.md + SQLite"
    )
    parser.add_argument("--channel", required=True, help="Channel slug")
    parser.add_argument(
        "--preset",
        default=DEFAULT_PRESET,
        help="Legacy preset slug (default: facebook_60_90)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    parser.add_argument(
        "--remove-legacy",
        action="store_true",
        help="Delete profile.toml and topics.json after migration",
    )
    args = parser.parse_args()

    if not channel_dir(args.channel).is_dir():
        print(f"Channel directory not found: {CHANNELS_DIR / args.channel}", file=sys.stderr)
        return 1

    try:
        migrate_channel(
            args.channel,
            args.preset,
            dry_run=args.dry_run,
            remove_legacy=args.remove_legacy,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
