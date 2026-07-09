"""Status-guarded transition functions for the Video Library.

Mirrors pipeline/lib/topics.py's pattern (validate current status, raise
ValueError on an invalid transition) but for the `videos`/`video_publications`
tables. Every transition writes through VideoLibraryStore's generic
_update_row + always appends a video_events row, so there is no risk of a
field being set on an in-memory object and silently dropped on write (the
bug this design deliberately avoids -- see video_library_store.py's
docstring).
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from app.services.video_library_store import VideoLibraryStore, utc_now_iso

_ARCHIVABLE_STATUSES = ("ready", "scheduled", "published", "failed")
_ROLLUP_ELIGIBLE_STATUSES = ("ready", "scheduled", "published")


def mark_ready(
    store: VideoLibraryStore,
    video_id: str,
    *,
    thumbnail_path: str | None = None,
    video_path: str | None = None,
    duration_seconds: float | None = None,
    file_size_bytes: int | None = None,
    keywords: list | None = None,
    actor: str = "system",
) -> dict[str, Any]:
    video = store.get_video(video_id)
    if not video:
        raise ValueError(f"video not found: {video_id}")

    fields: dict[str, Any] = {"status": "ready"}
    if thumbnail_path is not None:
        fields["thumbnail_path"] = thumbnail_path
    if video_path is not None:
        fields["video_path"] = video_path
    if duration_seconds is not None:
        fields["duration_seconds"] = duration_seconds
    if file_size_bytes is not None:
        fields["file_size_bytes"] = file_size_bytes
    if keywords is not None:
        fields["keywords"] = keywords

    store.update_video(video_id, **fields)
    store.add_event(
        video_id=video_id,
        type="status_changed",
        actor=actor,
        data={"from": video["status"], "to": "ready"},
    )
    return store.get_video(video_id)


def mark_failed(
    store: VideoLibraryStore, video_id: str, *, error: str | None = None, actor: str = "system"
) -> dict[str, Any]:
    video = store.get_video(video_id)
    if not video:
        raise ValueError(f"video not found: {video_id}")

    store.update_video(video_id, status="failed", error=str(error) if error else video.get("error"))
    store.add_event(
        video_id=video_id,
        type="error",
        actor=actor,
        data={"from": video["status"], "error": str(error) if error else None},
    )
    return store.get_video(video_id)


def mark_archived(store: VideoLibraryStore, video_id: str, *, actor: str = "user") -> dict[str, Any]:
    video = store.get_video(video_id)
    if not video:
        raise ValueError(f"video not found: {video_id}")
    if video["status"] not in _ARCHIVABLE_STATUSES:
        raise ValueError(
            f"video {video_id} must be one of {_ARCHIVABLE_STATUSES} to archive, "
            f"got '{video['status']}'"
        )

    store.update_video(video_id, status="archived")
    store.add_event(
        video_id=video_id, type="archived", actor=actor, data={"from": video["status"]}
    )
    return store.get_video(video_id)


def mark_restored(store: VideoLibraryStore, video_id: str, *, actor: str = "user") -> dict[str, Any]:
    video = store.get_video(video_id)
    if not video:
        raise ValueError(f"video not found: {video_id}")
    if video["status"] != "archived":
        raise ValueError(f"video {video_id} must be archived to restore, got '{video['status']}'")

    store.update_video(video_id, status="ready")
    store.add_event(
        video_id=video_id, type="status_changed", actor=actor, data={"from": "archived", "to": "ready"}
    )
    # Recompute in case the video had scheduled/published publications before
    # being archived -- restoring should reflect their current state, not
    # flatly drop back to "ready".
    return sync_rollup_status(store, video_id, actor=actor)


def sync_rollup_status(store: VideoLibraryStore, video_id: str, *, actor: str = "system") -> dict[str, Any]:
    """Recompute the video's rollup status from its current publications.

    Only touches videos in ready/scheduled/published -- draft/rendering/
    failed/archived are owned by their own lifecycle, not the publication
    rollup.
    """
    video = store.get_video(video_id)
    if not video or video["status"] not in _ROLLUP_ELIGIBLE_STATUSES:
        return video

    publications = store.list_publications(video_id)
    if any(p["status"] == "published" for p in publications):
        new_status = "published"
    elif any(p["status"] == "scheduled" for p in publications):
        new_status = "scheduled"
    else:
        new_status = "ready"

    if new_status != video["status"]:
        store.update_video(video_id, status=new_status)
        store.add_event(
            video_id=video_id,
            type="status_changed",
            actor=actor,
            data={"from": video["status"], "to": new_status},
        )
    return store.get_video(video_id)


def schedule_publications(
    store: VideoLibraryStore,
    video_id: str,
    *,
    platforms: list[str],
    provider: str,
    scheduled_at: str,
    actor: str = "user",
) -> list[dict[str, Any]]:
    created = []
    for platform in platforms:
        pub = store.create_publication(
            video_id=video_id,
            platform=platform,
            provider=provider,
            status="scheduled",
            scheduled_at=scheduled_at,
        )
        created.append(pub)
        store.add_event(
            video_id=video_id,
            type="scheduled",
            actor=actor,
            data={"platform": platform, "publication_id": pub["id"], "scheduled_at": scheduled_at},
        )
    sync_rollup_status(store, video_id, actor=actor)
    return created


def mark_publication_publishing(store: VideoLibraryStore, pub_id: str) -> dict[str, Any]:
    return store.update_publication(pub_id, status="publishing")


def mark_publication_published(
    store: VideoLibraryStore,
    pub_id: str,
    *,
    url: str | None = None,
    result: Any = None,
    actor: str = "user",
) -> dict[str, Any]:
    pub = store.update_publication(
        pub_id, status="published", published_at=utc_now_iso(), url=url, result=result
    )
    store.add_event(
        video_id=pub["video_id"],
        type="published",
        actor=actor,
        data={"platform": pub["platform"], "publication_id": pub_id, "url": url},
    )
    sync_rollup_status(store, pub["video_id"], actor=actor)
    return pub


def mark_publication_failed(
    store: VideoLibraryStore, pub_id: str, *, error: str | None = None, actor: str = "user"
) -> dict[str, Any]:
    pub = store.update_publication(pub_id, status="failed", error=str(error) if error else None)
    store.add_event(
        video_id=pub["video_id"],
        type="error",
        actor=actor,
        data={"platform": pub["platform"], "publication_id": pub_id, "error": str(error) if error else None},
    )
    sync_rollup_status(store, pub["video_id"], actor=actor)
    return pub


def cancel_publication(store: VideoLibraryStore, pub_id: str, *, actor: str = "user") -> dict[str, Any]:
    pub = store.get_publication(pub_id)
    if not pub:
        raise ValueError(f"publication not found: {pub_id}")
    if pub["status"] not in ("scheduled", "publishing"):
        raise ValueError(
            f"publication {pub_id} must be scheduled/publishing to cancel, got '{pub['status']}'"
        )

    store.update_publication(pub_id, status="cancelled")
    store.add_event(
        video_id=pub["video_id"],
        type="cancelled",
        actor=actor,
        data={"platform": pub["platform"], "publication_id": pub_id},
    )
    sync_rollup_status(store, pub["video_id"], actor=actor)
    return store.get_publication(pub_id)


def record_re_render(store: VideoLibraryStore, old_video_id: str, new_video_id: str, *, actor: str = "user") -> None:
    store.add_event(
        video_id=old_video_id,
        type="re_rendered",
        actor=actor,
        data={"new_video_id": new_video_id},
    )


def record_stage_event(task_id: str, stage: str, started_at_monotonic: float, *, actor: str = "system") -> None:
    """Fire-and-forget stage-timing event. Never raises -- a logging failure
    must never break an actual render (called from inside task.py::start()).
    """
    try:
        elapsed_seconds = time.monotonic() - started_at_monotonic
        store = VideoLibraryStore()
        store.add_event(
            video_id=task_id,
            type="stage_completed",
            actor=actor,
            data={"stage": stage, "elapsed_seconds": round(elapsed_seconds, 3)},
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad, must never break a render
        logger.warning(f"failed to record stage-timing event for {task_id}/{stage}: {exc}")
