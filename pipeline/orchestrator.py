#!/usr/bin/env python3
"""Pipeline orchestrator — editorial layer for MoneyPrinterTurbo."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from loguru import logger

# Allow running as: python pipeline/orchestrator.py
_PIPELINE_DIR = Path(__file__).resolve().parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from lib.api_client import ApiClient, ApiError  # noqa: E402
from lib.channel import ROOT_DIR, load_channel, load_settings  # noqa: E402
from lib import music as music_lib  # noqa: E402
from lib import topics as topics_lib  # noqa: E402
from lib.topic_store import TopicStore  # noqa: E402

RUNS_DIR = _PIPELINE_DIR / "runs"


def _first_or_none(values: Any) -> str | None:
    if isinstance(values, list) and values:
        return str(values[0])
    if isinstance(values, str) and values:
        return values
    return None


def resolve_local_path(path_or_uri: str | None, task_id: str) -> str | None:
    if not path_or_uri:
        return None

    raw = str(path_or_uri)
    candidates: list[Path] = []

    if raw.startswith("/tasks/"):
        candidates.append(ROOT_DIR / "storage" / raw.lstrip("/"))
    elif raw.startswith("tasks/"):
        candidates.append(ROOT_DIR / "storage" / raw)
    elif Path(raw).is_absolute():
        candidates.append(Path(raw))
    else:
        candidates.append(ROOT_DIR / raw)

    task_dir = ROOT_DIR / "storage" / "tasks" / task_id
    candidates.extend(
        [
            task_dir / "final-1.mp4",
            task_dir / "combined-1.mp4",
            task_dir / Path(raw).name,
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return raw


def build_video_payload(
    config: dict[str, Any], topic: str, *, bgm_file: str = ""
) -> dict[str, Any]:
    subtitle_bg_enabled = config.get("subtitle_background_enabled", True)
    if subtitle_bg_enabled:
        text_background_color = config.get("subtitle_background_color", "#000000")
    else:
        text_background_color = False

    return {
        "video_subject": topic,
        "video_script": "",
        "video_language": config.get("video_language", "pt-BR"),
        "paragraph_number": config.get("paragraph_number", 3),
        "video_script_prompt": (config.get("video_script_prompt") or "").strip(),
        "voice_name": config.get("voice_name", ""),
        "voice_volume": config.get("voice_volume", 1.0),
        "voice_rate": config.get("voice_rate", 1.0),
        "video_source": config.get("video_source", "pexels"),
        "video_aspect": config.get("video_aspect", "9:16"),
        "video_concat_mode": config.get("video_concat_mode", "random"),
        "video_transition_mode": config.get("video_transition_mode"),
        "video_clip_duration": config.get("video_clip_duration", 3),
        "video_count": config.get("video_count", 1),
        "font_name": config.get("font_name", "Roboto-Bold.ttf"),
        "font_size": config.get("font_size", 55),
        "subtitle_enabled": config.get("subtitle_enabled", True),
        "subtitle_position": config.get("subtitle_position", "bottom"),
        "custom_position": config.get("custom_position", 70.0),
        "text_fore_color": config.get("text_fore_color", "#FFFFFF"),
        "stroke_color": config.get("stroke_color", "#000000"),
        "stroke_width": config.get("stroke_width", 2.5),
        "text_background_color": text_background_color,
        "rounded_subtitle_background": config.get(
            "rounded_subtitle_background", False
        ),
        "bgm_type": "custom" if bgm_file else config.get("bgm_type", "random"),
        "bgm_file": bgm_file,
        "bgm_profile": config.get("bgm_profile", ""),
        "bgm_volume": config.get("bgm_volume", 0.2),
        "n_threads": config.get("n_threads", 2),
        "match_materials_to_script": bool(
            config.get("match_materials_to_script", False)
        ),
        "collector_target_clips": (config.get("collector") or {}).get("target_clips", 25),
        "collector_min_acceptable_clips": (config.get("collector") or {}).get(
            "min_acceptable_clips", 20
        ),
        "channel_slug": config.get("slug", ""),
    }


def resolve_topic_bgm(topic: dict[str, Any]) -> tuple[str, list[str], str, str]:
    """Return (selected_profile, music_profiles, bgm_file_api_path, bgm_filename)."""
    profiles = music_lib.normalize_music_profiles(topic)
    profile = music_lib.pick_music_profile(topic)
    music_file = music_lib.pick_random_music(profile)
    if music_file is None:
        raise FileNotFoundError(
            f"No music files for profile {profile!r} in {music_lib.MUSIC_DIR}"
        )
    return (
        profile,
        profiles,
        music_lib.music_path_for_api(music_file),
        music_file.name,
    )


def save_run_meta(channel: str, meta: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = str(
        meta.get("run_id")
        or f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S_%f')}_{channel}"
    )
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_path = run_dir / "meta.json"
    enriched_meta = dict(meta)
    enriched_meta["run_id"] = run_id
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(enriched_meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return meta_path


def cmd_stats(channel: str, store: TopicStore) -> int:
    counts = store.count_by_status(channel)

    labels = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("generated", "Generated"),
        ("approved", "Approved"),
        ("failed", "Failed"),
        ("published", "Published"),
    ]
    for key, label in labels:
        print(f"{label}: {counts.get(key, 0)}")
    return 0


def cmd_approve(channel: str, topic_id: int, store: TopicStore) -> int:
    topic = store.find_by_id(channel, topic_id)
    if not topic:
        print(f"Topic id={topic_id} not found.", file=sys.stderr)
        return 1
    try:
        topics_lib.mark_approved(topic)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    store.update_topic(channel, topic)
    print(f"Approved topic id={topic_id}: {topic.get('topic')}")
    return 0


def cmd_publish(channel: str, topic_id: int, store: TopicStore) -> int:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from lib.publish_profiles import (  # noqa: E402
        USE_CHANNEL_PUBLISH_PROFILES,
        resolve_config_publish_platforms,
        resolve_publish_platforms,
    )
    from app.services import publish as publish_service  # noqa: E402

    topic = store.find_by_id(channel, topic_id)
    if not topic:
        print(f"Topic id={topic_id} not found.", file=sys.stderr)
        return 1

    config = load_channel(channel)
    if USE_CHANNEL_PUBLISH_PROFILES or publish_service.get_backend_name() == "zernio":
        platforms, skipped, youtube_privacy = resolve_publish_platforms(config)
    else:
        platforms, skipped, youtube_privacy = resolve_config_publish_platforms()
    if not platforms:
        print(
            "No enabled publish platforms for this channel. "
            "Check publish_profiles in channel.json.",
            file=sys.stderr,
        )
        for item in skipped:
            print(
                f"  skipped {item.get('platform')}: {item.get('reason')}",
                file=sys.stderr,
            )
        return 1

    backend_name = publish_service.get_backend_name()
    if not publish_service.get_active_service().is_configured():
        print(
            f"Publish backend '{backend_name}' is not configured. "
            f"Set {backend_name}_* in config.toml.",
            file=sys.stderr,
        )
        return 1

    video_path = topic.get("video_path")
    task_id = topic.get("task_id")
    if not video_path:
        print(f"Topic id={topic_id} has no video_path.", file=sys.stderr)
        return 1

    resolved_path = resolve_local_path(str(video_path), str(task_id or ""))
    if not resolved_path:
        print(f"Video file not found for topic id={topic_id}.", file=sys.stderr)
        return 1

    settings = load_settings()
    script = ""
    try:
        client = ApiClient(
            base_url=settings.get("api_base_url", "http://127.0.0.1:8080"),
            poll_interval=float(settings.get("poll_interval_seconds", 5)),
            poll_timeout=float(settings.get("poll_timeout_seconds", 60)),
        )
        if task_id:
            task = client.get_task(str(task_id))
            script = str(task.get("script") or "")
    except Exception as exc:
        logger.warning(f"Could not fetch task script for publish: {exc}")

    subject = str(topic.get("topic") or "")
    language = str(config.get("video_language") or "pt-BR")

    print(f"Publishing topic id={topic_id} to: {', '.join(platforms)}")
    results = publish_service.cross_post_videos(
        video_paths=[resolved_path],
        subject=subject,
        script=script,
        language=language,
        platforms=platforms,
        youtube_privacy_status=youtube_privacy,
    )

    if not any(r.get("success") for r in results):
        print("Publish failed.", file=sys.stderr)
        for result in results:
            print(f"  {result.get('error', result)}", file=sys.stderr)
        return 1

    try:
        topics_lib.mark_published(topic, platforms=platforms, results=results)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    store.update_topic(channel, topic)

    meta = {
        "channel": channel,
        "channel_name": config.get("name"),
        "topic_id": topic["id"],
        "topic": subject,
        "task_id": task_id,
        "video_path": resolved_path,
        "publish_platforms": platforms,
        "publish_results": results,
        "skipped_publish_profiles": skipped,
        "status": "published",
        "published_at": topic.get("published_at"),
    }
    meta_path = save_run_meta(channel, meta)
    print(f"Published topic id={topic_id}")
    print(f"Meta: {meta_path}")
    return 0


def cmd_retry(channel: str, topic_id: int, store: TopicStore) -> int:
    topic = store.find_by_id(channel, topic_id)
    if not topic:
        print(f"Topic id={topic_id} not found.", file=sys.stderr)
        return 1
    try:
        topics_lib.mark_retry(topic)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    store.update_topic(channel, topic)
    print(f"Retry queued topic id={topic_id}: {topic.get('topic')}")
    return 0


def cmd_dry_run(channel: str) -> int:
    config = load_channel(channel)
    store = TopicStore()
    topic = store.get_next_pending(channel)
    if not topic:
        print("No pending topics.")
        return 0
    try:
        topics_lib.prepare_topic(topic)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Channel: {config.get('name', channel)}")
    print(f"Next topic id={topic['id']} [{topic.get('category')}]")
    print(f"Music profiles: {music_lib.normalize_music_profiles(topic)}")
    print(f"Topic: {topic.get('topic')}")
    print(f"Status: {topic.get('status')}")
    return 0


def cmd_generate(channel: str, topic_id: int | None = None) -> int:
    settings = load_settings()
    config = load_channel(channel)
    store = TopicStore()

    if topic_id is not None:
        topic = store.find_by_id(channel, topic_id)
        if not topic:
            print(f"Topic id={topic_id} not found.", file=sys.stderr)
            return 1
        if topic.get("status") != "pending":
            print(
                f"Topic id={topic_id} is not pending (status={topic.get('status')}).",
                file=sys.stderr,
            )
            return 1
    else:
        topic = store.get_next_pending(channel)
        if not topic:
            print("No pending topics.")
            return 0

    try:
        topics_lib.prepare_topic(topic)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    topics_lib.mark_processing(topic)
    store.update_topic(channel, topic)

    client = ApiClient(
        base_url=settings.get("api_base_url", "http://127.0.0.1:8080"),
        poll_interval=float(settings.get("poll_interval_seconds", 5)),
        poll_timeout=float(settings.get("poll_timeout_seconds", 1800)),
    )

    try:
        music_profile, music_profiles, bgm_file, bgm_name = resolve_topic_bgm(topic)
    except FileNotFoundError as exc:
        topics_lib.mark_failed(topic)
        store.update_topic(channel, topic)
        print(str(exc), file=sys.stderr)
        return 1

    payload = build_video_payload(config, topic["topic"], bgm_file=bgm_file)
    task_id: str | None = None

    try:
        print(f"Generating topic id={topic['id']}: {topic['topic']}")
        print(f"BGM: {music_profile}/{bgm_name} (pool: {music_profiles})")
        task_id = client.create_video(payload)
        print(f"Task created: {task_id}")
        task = client.wait_for_task(task_id)

        raw_final = _first_or_none(task.get("videos"))
        raw_combined = _first_or_none(task.get("combined_videos"))
        final_video = resolve_local_path(raw_final, task_id)
        combined_video = resolve_local_path(raw_combined, task_id)
        video_path = final_video or combined_video or raw_final or ""

        topics_lib.mark_generated(
            topic, task_id=task_id, video_path=video_path or ""
        )
        store.update_topic(channel, topic)

        meta = {
            "channel": channel,
            "channel_name": config.get("name"),
            "target_duration": config.get("target_duration"),
            "uid": topic.get("uid"),
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "topic_hash": topic.get("topic_hash"),
            "category": topic.get("category"),
            "music_profile": music_profile,
            "music_profiles": music_profiles,
            "bgm_file": bgm_file,
            "bgm_name": bgm_name,
            "task_id": task_id,
            "video_path": video_path,
            "final_video": final_video or raw_final,
            "combined_video": combined_video or raw_combined,
            "script": task.get("script", ""),
            "status": "generated",
            "generated_at": topic.get("generated_at"),
        }
        meta_path = save_run_meta(channel, meta)
        print(f"Done. Video: {video_path}")
        print(f"Meta: {meta_path}")
        return 0

    except (ApiError, requests.HTTPError) as exc:
        topics_lib.mark_failed(topic, task_id=task_id)
        store.update_topic(channel, topic)
        meta = {
            "channel": channel,
            "channel_name": config.get("name"),
            "uid": topic.get("uid"),
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "topic_hash": topic.get("topic_hash"),
            "category": topic.get("category"),
            "music_profile": music_profile,
            "music_profiles": music_profiles,
            "bgm_file": bgm_file,
            "bgm_name": bgm_name,
            "task_id": task_id,
            "status": "failed",
            "error": str(exc),
            "generated_at": topics_lib.utc_now_iso(),
        }
        meta_path = save_run_meta(channel, meta)
        print(f"Failed: {exc}", file=sys.stderr)
        print(f"Meta: {meta_path}", file=sys.stderr)
        return 1
    except Exception as exc:
        topics_lib.mark_failed(topic, task_id=task_id)
        store.update_topic(channel, topic)
        meta = {
            "channel": channel,
            "channel_name": config.get("name"),
            "uid": topic.get("uid"),
            "topic_id": topic["id"],
            "topic": topic["topic"],
            "topic_hash": topic.get("topic_hash"),
            "category": topic.get("category"),
            "music_profile": music_profile,
            "music_profiles": music_profiles,
            "bgm_file": bgm_file,
            "bgm_name": bgm_name,
            "task_id": task_id,
            "status": "failed",
            "error": str(exc),
            "generated_at": topics_lib.utc_now_iso(),
        }
        meta_path = save_run_meta(channel, meta)
        print(f"Failed: {exc}", file=sys.stderr)
        print(f"Meta: {meta_path}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="MoneyPrinterTurbo pipeline orchestrator")
    parser.add_argument("--channel", required=True, help="Channel slug (e.g. japao)")
    parser.add_argument("--dry-run", action="store_true", help="Show next pending topic")
    parser.add_argument("--approve", type=int, metavar="ID", help="Approve generated topic")
    parser.add_argument("--publish", type=int, metavar="ID", help="Publish approved topic")
    parser.add_argument("--retry", type=int, metavar="ID", help="Reset failed topic to pending")
    parser.add_argument("--stats", action="store_true", help="Show topic counts by status")
    parser.add_argument(
        "--topic-id",
        type=int,
        metavar="ID",
        help="Generate a specific pending topic by id",
    )
    args = parser.parse_args()

    try:
        load_channel(args.channel)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    store = TopicStore()

    if args.stats:
        return cmd_stats(args.channel, store)
    if args.approve is not None:
        return cmd_approve(args.channel, args.approve, store)
    if args.publish is not None:
        return cmd_publish(args.channel, args.publish, store)
    if args.retry is not None:
        return cmd_retry(args.channel, args.retry, store)
    if args.dry_run:
        return cmd_dry_run(args.channel)
    return cmd_generate(args.channel, topic_id=args.topic_id)


if __name__ == "__main__":
    raise SystemExit(main())
