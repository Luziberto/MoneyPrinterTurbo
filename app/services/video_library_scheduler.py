"""Per-minute due-publications scan.

No in-process background scheduler (no APScheduler/Celery) -- this is meant
to be invoked by a cron-triggered script (app/scripts/run_due_publications.py),
consistent with how pipeline/orchestrator.py is already invoked via crontab.
Also reachable manually via POST /video-library/run-due-publications.
"""

from __future__ import annotations

import os

from loguru import logger

from app.services import publish, task_assets
from app.services import video_library_transitions as transitions
from app.services.video_library_store import VideoLibraryStore


def run_due_publications(now_iso: str | None = None) -> list[dict]:
    store = VideoLibraryStore()
    due = store.list_due_publications(now_iso)
    if not due:
        return []

    by_video: dict[str, list[dict]] = {}
    for pub in due:
        by_video.setdefault(pub["video_id"], []).append(pub)

    processed: list[dict] = []
    for video_id, pubs in by_video.items():
        video = store.get_video(video_id)
        if not video or not video.get("video_path") or not os.path.isfile(video["video_path"]):
            for pub in pubs:
                transitions.mark_publication_failed(
                    store, pub["id"], error="video file not found on disk", actor="scheduler"
                )
                processed.append({"publication_id": pub["id"], "video_id": video_id, "success": False})
            continue

        platforms = [pub["platform"] for pub in pubs]
        script = task_assets.read_script_json(video_id) or {}
        try:
            result = publish.cross_post_videos(
                video_paths=[video["video_path"]],
                subject=video["subject"],
                script=script.get("script", ""),
                platforms=platforms,
            )[0]
        except Exception as exc:  # noqa: BLE001 - one video's failure must not abort the scan
            logger.warning(f"scheduled publish failed for video {video_id}: {exc}")
            result = {"success": False, "error": str(exc)}

        for pub in pubs:
            if result.get("success"):
                transitions.mark_publication_published(
                    store, pub["id"],
                    url=result.get("post_id") or result.get("request_id"),
                    result=result,
                    actor="scheduler",
                )
            else:
                transitions.mark_publication_failed(
                    store, pub["id"], error=result.get("error", "publish failed"), actor="scheduler"
                )
            processed.append(
                {"publication_id": pub["id"], "video_id": video_id, "success": bool(result.get("success"))}
            )

    return processed
