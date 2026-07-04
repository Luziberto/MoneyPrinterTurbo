#!/usr/bin/env python3
"""One-shot migration: Portuguese category slugs → English in topic store."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from lib.categories import VALID_CATEGORIES, normalize_category  # noqa: E402
from lib.topic_store import TopicStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate topic categories PT → EN")
    parser.add_argument("--channel", required=True, help="Channel slug")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    store = TopicStore()
    topics = store.list_topics(args.channel)
    if not topics:
        print(f"No topics found for channel {args.channel!r}.", file=sys.stderr)
        return 1

    migrated = 0
    unknown: list[str] = []
    for topic in topics:
        old = topic.get("category", "")
        new = normalize_category(str(old))
        if new != old:
            migrated += 1
            print(f"  id={topic['id']}: {old!r} → {new!r}")
            if not args.dry_run:
                topic["category"] = new
                store.update_topic(args.channel, topic)
        if new not in VALID_CATEGORIES:
            unknown.append(f"id={topic.get('id')}: {new!r}")

    if unknown:
        print("Unknown categories after migration:", unknown, file=sys.stderr)
        return 1

    counts = Counter(t["category"] for t in topics)
    print(f"Migrated {migrated} topics. Distribution: {dict(counts)}")

    if args.dry_run:
        print("(dry-run — database not modified)")
        return 0

    print(f"Updated topics in {store.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
