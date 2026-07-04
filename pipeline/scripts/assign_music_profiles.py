#!/usr/bin/env python3
"""Assign music_profiles to topics from category defaults (preparation only)."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from lib.categories import music_profiles_for_category  # noqa: E402
from lib.channel import load_channel  # noqa: E402
from lib.topic_store import TopicStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assign music_profiles from CATEGORY_MUSIC_DEFAULTS"
    )
    parser.add_argument("--channel", required=True, help="Channel slug")
    args = parser.parse_args()

    channel = load_channel(args.channel)
    music_profile_overrides = channel.get("music_profile_overrides")
    store = TopicStore()
    topics = store.list_topics(args.channel)
    if not topics:
        print(f"No topics found for channel {args.channel!r}.", file=sys.stderr)
        return 1

    for topic in topics:
        profiles = music_profiles_for_category(
            topic.get("category", ""),
            music_profile_overrides,
        )
        topic["music_profiles"] = profiles
        store.update_topic(args.channel, topic)

    counts = Counter(p for t in topics for p in t["music_profiles"])
    print("Profile pool counts (topics may list multiple):", dict(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
