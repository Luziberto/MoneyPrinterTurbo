#!/usr/bin/env python3
"""Generate topics via GPT and store in SQLite — preparation only."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[1]
_ROOT_DIR = _PIPELINE_DIR.parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from lib.categories import (  # noqa: E402
    VALID_CATEGORIES,
    music_profiles_for_category,
    topic_distribution_for_channel,
)
from lib.channel import load_channel  # noqa: E402
from lib import topics as topics_lib  # noqa: E402
from lib.topic_store import TopicStore  # noqa: E402

TOPIC_LANGUAGE_HINTS = {
    "pt-BR": "Brazilian Portuguese",
    "pt": "Brazilian Portuguese",
    "en": "English",
    "en-US": "English",
}


def _topic_language_label(video_language: str) -> str:
    return TOPIC_LANGUAGE_HINTS.get(video_language, video_language or "the channel language")


def build_generation_prompt(
    *,
    niche: str,
    count: int,
    video_language: str,
    distribution: dict[str, int],
    existing_topics: list[str],
) -> str:
    categories_block = "\n".join(f"- {cat}" for cat in sorted(VALID_CATEGORIES))
    distribution_block = "\n".join(
        f"- {cat}: {n}" for cat, n in sorted(distribution.items())
    )
    avoid_block = ""
    if existing_topics:
        sample = existing_topics[:30]
        avoid_block = (
            "\n\nDo not repeat or closely paraphrase these existing topics:\n"
            + "\n".join(f"- {t}" for t in sample)
        )

    lang = _topic_language_label(video_language)
    return f"""Generate {count} unique short-form video topic ideas about {niche}.

Allowed categories (use exactly these English slugs in "category"):
{categories_block}

Target distribution per category:
{distribution_block}

Rules:
- Return a JSON array only. No markdown fences, no commentary.
- Each item: {{"category": "<slug>", "topic": "<question or hook>"}}
- "category" must be one of the allowed English slugs above.
- "topic" must be written in {lang}.
- Each topic must be a single curiosity — one video = one question.
- Do not repeat subjects.{avoid_block}

Example item:
{{"category": "culture", "topic": "Por que os japoneses tiram os sapatos antes de entrar em casa?"}}
"""


def _parse_topics_json(raw: str) -> list[dict]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("GPT response is not a JSON array")

    items: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        category = str(entry.get("category", "")).strip()
        topic = str(entry.get("topic", "")).strip()
        if category and topic:
            items.append({"category": category, "topic": topic})
    return items


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = item["topic"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def generate_for_category(
    *,
    niche: str,
    category: str,
    count: int,
    video_language: str,
    existing_topics: list[str],
) -> list[dict]:
    from app.services import llm  # noqa: WPS433

    prompt = build_generation_prompt(
        niche=niche,
        count=count,
        video_language=video_language,
        distribution={category: count},
        existing_topics=existing_topics,
    )
    raw = llm._generate_response(prompt)
    parsed = _parse_topics_json(raw)
    valid = [i for i in parsed if i["category"] == category]
    return valid[:count]


def build_topic_records(
    items: list[dict],
    start_id: int = 1,
    *,
    music_profile_overrides: dict[str, list[str]] | None = None,
) -> list[dict]:
    records = []
    for offset, item in enumerate(items):
        topic_text = item["topic"]
        category = item["category"]
        records.append(
            {
                "id": start_id + offset,
                "category": category,
                "music_profiles": music_profiles_for_category(
                    category, music_profile_overrides
                ),
                "topic": topic_text,
                "topic_hash": topics_lib.topic_hash(topic_text),
                "status": "pending",
                "generated_at": None,
                "task_id": None,
                "video_path": None,
                "approved": False,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate topics via GPT into SQLite")
    parser.add_argument("--channel", required=True, help="Channel slug")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated topics without writing to database",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace all topics for the channel (default: refuse if topics exist)",
    )
    args = parser.parse_args()

    channel = load_channel(args.channel)
    niche = channel.get("niche", "Japan")
    video_language = channel.get("video_language", "pt-BR")
    topic_distribution = topic_distribution_for_channel(
        channel.get("topic_distribution")
    )
    music_profile_overrides = channel.get("music_profile_overrides")
    store = TopicStore()

    existing: list[str] = []
    if store.has_topics(args.channel) and not args.overwrite:
        if not args.dry_run:
            print(
                f"Topics already exist for channel {args.channel!r}. "
                "Use --overwrite or --dry-run.",
                file=sys.stderr,
            )
            return 1
        existing = store.existing_topic_texts(args.channel)

    all_items: list[dict] = []
    for category, count in sorted(topic_distribution.items()):
        print(f"Generating {count} topics for [{category}]...")
        batch = generate_for_category(
            niche=niche,
            category=category,
            count=count,
            video_language=video_language,
            existing_topics=existing + [i["topic"] for i in all_items],
        )
        if len(batch) < count:
            print(
                f"Warning: got {len(batch)}/{count} for {category}",
                file=sys.stderr,
            )
        all_items.extend(batch)

    all_items = _dedupe_items(all_items)
    start_id = 1 if args.overwrite else store.next_id(args.channel)
    records = build_topic_records(
        all_items,
        start_id=start_id,
        music_profile_overrides=music_profile_overrides,
    )

    invalid = [r for r in records if r["category"] not in VALID_CATEGORIES]
    if invalid:
        print(f"Invalid categories in output: {invalid[:3]}", file=sys.stderr)
        return 1

    print(f"Generated {len(records)} topics.")
    if args.dry_run:
        print(json.dumps(records[:5], ensure_ascii=False, indent=2))
        print(f"... ({len(records)} total, not saved)")
        return 0

    if args.overwrite:
        store.clear_channel(args.channel)
        start_id = 1
        records = build_topic_records(
            all_items,
            start_id=start_id,
            music_profile_overrides=music_profile_overrides,
        )

    inserted = store.insert_topics(args.channel, records, replace=False)
    print(f"Saved {inserted} topics to {store.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
