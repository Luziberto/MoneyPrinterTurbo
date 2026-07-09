"""Topic list load/save and status transitions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.categories import VALID_CATEGORIES, music_profiles_for_category
from lib.music import VALID_PROFILES

VALID_STATUSES = frozenset(
    {"pending", "processing", "generated", "failed", "approved", "published"}
)

GENERATED_VIDEO_STATUSES = frozenset({"generated", "approved", "published"})


def topic_hash(topic: str) -> str:
    normalized = (topic or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _topic_label(topic: dict[str, Any]) -> str:
    return f"Topic id={topic.get('id', '?')}"


def prepare_topic(topic: dict[str, Any]) -> None:
    """Validate editorial fields and derive music_profiles when absent."""
    label = _topic_label(topic)

    topic_text = (topic.get("topic") or "").strip()
    if not topic_text:
        raise ValueError(f"{label}: 'topic' is required")

    category = topic.get("category")
    if not category:
        raise ValueError(f"{label}: 'category' is required")
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"{label}: invalid category {category!r}. "
            f"Expected one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    profiles = topic.get("music_profiles")
    if not profiles:
        topic["music_profiles"] = music_profiles_for_category(str(category))
        return

    if not isinstance(profiles, list):
        raise ValueError(f"{label}: 'music_profiles' must be a list")

    normalized = [
        str(profile).strip() for profile in profiles if str(profile).strip()
    ]
    if not normalized:
        raise ValueError(
            f"{label}: 'music_profiles' is empty. "
            "Omit the field to derive from category or set valid profiles."
        )

    invalid = [p for p in normalized if p not in VALID_PROFILES]
    if invalid:
        raise ValueError(
            f"{label}: invalid music profile(s): {', '.join(invalid)}. "
            f"Expected subset of: {', '.join(sorted(VALID_PROFILES))}"
        )

    topic["music_profiles"] = normalized


def load_topics(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"topics file must be a JSON array: {path}")
    return data


def save_topics(path: Path, topics: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)
        f.write("\n")


def find_topic(topics: list[dict[str, Any]], topic_id: int) -> dict[str, Any] | None:
    for item in topics:
        if item.get("id") == topic_id:
            return item
    return None


def get_next_pending(topics: list[dict[str, Any]]) -> dict[str, Any] | None:
    pending = [t for t in topics if t.get("status") == "pending"]
    if not pending:
        return None
    return min(pending, key=lambda t: t.get("id", 0))


def count_by_status(topics: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    for item in topics:
        status = item.get("status", "pending")
        if status in counts:
            counts[status] += 1
        else:
            counts[status] = counts.get(status, 0) + 1
    return counts


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def mark_processing(topic: dict[str, Any]) -> None:
    topic["status"] = "processing"


def mark_generated(
    topic: dict[str, Any],
    *,
    task_id: str,
    video_path: str,
) -> None:
    topic["status"] = "generated"
    topic["task_id"] = task_id
    topic["video_path"] = video_path
    topic["generated_at"] = utc_now_iso()
    topic["approved"] = False


def mark_failed(topic: dict[str, Any], *, task_id: str | None = None) -> None:
    topic["status"] = "failed"
    if task_id:
        topic["task_id"] = task_id


def mark_approved(topic: dict[str, Any]) -> None:
    if topic.get("status") != "generated":
        raise ValueError(
            f"Topic {topic.get('id')} must be 'generated' to approve, "
            f"got '{topic.get('status')}'"
        )
    topic["status"] = "approved"
    topic["approved"] = True


def mark_published(
    topic: dict[str, Any],
    *,
    platforms: list[str],
    results: list[dict[str, Any]],
) -> None:
    if topic.get("status") != "approved":
        raise ValueError(
            f"Topic {topic.get('id')} must be 'approved' to publish, "
            f"got '{topic.get('status')}'"
        )
    topic["status"] = "published"
    topic["published_at"] = utc_now_iso()
    topic["publish_platforms"] = list(platforms)
    topic["publish_results"] = results


def mark_retry(topic: dict[str, Any]) -> None:
    if topic.get("status") != "failed":
        raise ValueError(
            f"Topic {topic.get('id')} must be 'failed' to retry, "
            f"got '{topic.get('status')}'"
        )
    topic["status"] = "pending"
    topic["task_id"] = None
    topic["video_path"] = None
    topic["generated_at"] = None
    topic["approved"] = False
