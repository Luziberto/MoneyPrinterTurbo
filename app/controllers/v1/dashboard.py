"""Dashboard aggregator -- status counts, time-window cards, provider health,
stage-timing averages, recent videos/errors, disk usage, and queue summary.

Everything here is read-only and derived from existing stores (VideoLibraryStore,
app.services.state, runtime_limits, provider_readiness) -- no new persistence.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.config import config
from app.controllers.v1.base import new_router
from app.services import provider_readiness
from app.services import state as sm
from app.services.video_library_store import VideoLibraryStore
from app.utils import utils

router = new_router()

_STAGES = ("script", "terms", "tts", "collector", "render", "upload")


def _window_starts_iso() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    return {
        "today": today_start.isoformat(),
        "this_week": week_start.isoformat(),
        "this_month": month_start.isoformat(),
    }


@router.get("/dashboard/summary", response_model=None, summary="Aggregated dashboard metrics")
def get_dashboard_summary(request: Request):
    from app.services import runtime_limits

    store = VideoLibraryStore()

    status_counts = store.count_by_status()
    windows = _window_starts_iso()
    time_window_counts = {
        label: store.count_created_since(since_iso) for label, since_iso in windows.items()
    }

    recent_videos, _ = store.list_videos(page=1, page_size=6)
    recent_errors = store.recent_failed(limit=5)

    stage_timing = {stage: store.avg_stage_seconds(stage) for stage in _STAGES}

    disk = shutil.disk_usage(utils.storage_dir())

    estimated_minutes_per_video = float(config.app.get("estimated_manual_minutes_per_video", 20))
    videos_reached_ready = store.count_reached_ready()

    tasks, total_tasks = sm.state.get_all_tasks(1, 10)

    return utils.get_response(
        200,
        {
            "status_counts": status_counts,
            "time_window_counts": time_window_counts,
            "provider_health": provider_readiness.all_readiness("pexels", ""),
            "recent_videos": recent_videos,
            "recent_errors": recent_errors,
            "stage_timing_avg_seconds": stage_timing,
            "disk_usage": {"total": disk.total, "used": disk.used, "free": disk.free},
            "estimated_minutes_saved": {
                "minutes": estimated_minutes_per_video * videos_reached_ready,
                "videos_counted": videos_reached_ready,
                "minutes_per_video": estimated_minutes_per_video,
                "is_estimate": True,
            },
            "queue": {
                "lock": runtime_limits.generation_lock_status(),
                "recent_tasks": tasks,
                "total_tasks": total_tasks,
            },
        },
    )
