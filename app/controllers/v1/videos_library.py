"""Video Library API -- list/detail/publish/schedule/archive/re-render.

Decouples publishing from rendering: a completed render lands in the
library (see app/services/video_library_transitions.py::mark_ready, wired
from app/services/task.py) and everything here operates on that persisted
row, never on the live task state.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Optional

from fastapi import Path, Query, Request
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import publish, task_assets
from app.services.video_library_store import VideoLibraryStore
from app.services import video_library_transitions as transitions
from app.utils import utils

router = new_router()

VALID_STATUSES = (
    "draft", "rendering", "ready", "scheduled", "published", "archived", "failed",
)
VALID_PLATFORMS = ("tiktok", "instagram", "youtube", "facebook")


def _store() -> VideoLibraryStore:
    return VideoLibraryStore()


def _get_video_or_404(store: VideoLibraryStore, request: Request, video_id: str) -> dict:
    request_id = base.get_task_id(request)
    video = store.get_video(video_id)
    if not video:
        raise HttpException(
            task_id=request_id, status_code=404, message=f"{request_id}: video not found: {video_id}"
        )
    return video


@router.get("/video-library", response_model=None, summary="List videos in the library")
def list_videos(
    request: Request,
    status: Optional[str] = Query(default=None),
    channel_slug: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    request_id = base.get_task_id(request)
    if status and status not in VALID_STATUSES:
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: invalid status: {status}"
        )
    store = _store()
    videos, total = store.list_videos(
        status=status, channel_slug=channel_slug, tag=tag,
        date_from=date_from, date_to=date_to, q=q, page=page, page_size=page_size,
    )
    return utils.get_response(
        200, {"videos": videos, "total": total, "page": page, "page_size": page_size}
    )


@router.get("/video-library/{video_id}", response_model=None, summary="Video detail: row + script + publications + assets")
def get_video_detail(request: Request, video_id: str = Path(...)):
    store = _store()
    video = _get_video_or_404(store, request, video_id)
    return utils.get_response(
        200,
        {
            **video,
            "script": task_assets.read_script_json(video_id),
            "publications": store.list_publications(video_id),
            "assets": [asdict(a) for a in task_assets.list_assets(video_id)],
            "events": store.list_events(video_id),
        },
    )


class VideoPatchRequest(BaseModel):
    title: Optional[str] = None
    tags: Optional[list[str]] = None
    caption: Optional[str] = None


@router.patch("/video-library/{video_id}", response_model=None, summary="Update video metadata")
def patch_video(request: Request, body: VideoPatchRequest, video_id: str = Path(...)):
    store = _store()
    _get_video_or_404(store, request, video_id)

    fields = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.tags is not None:
        fields["tags"] = body.tags
    if body.caption is not None:
        fields["caption"] = body.caption

    if fields:
        store.update_video(video_id, **fields)
        store.add_event(video_id=video_id, type="title_changed", actor="user", data=fields)

    return utils.get_response(200, store.get_video(video_id))


@router.delete("/video-library/{video_id}", response_model=None, summary="Hard-delete a video and its task directory")
def delete_video(request: Request, video_id: str = Path(...)):
    import shutil

    store = _store()
    _get_video_or_404(store, request, video_id)
    store.delete_video(video_id)
    shutil.rmtree(utils.task_dir(video_id), ignore_errors=True)
    return utils.get_response(200, {"deleted": True})


class PublishRequest(BaseModel):
    platforms: list[str]
    youtube_privacy_status: Optional[str] = None


@router.post("/video-library/{video_id}/publish", response_model=None, summary="Publish now to one or more platforms")
def publish_now(request: Request, body: PublishRequest, video_id: str = Path(...)):
    request_id = base.get_task_id(request)
    store = _store()
    video = _get_video_or_404(store, request, video_id)

    if not body.platforms or any(p not in VALID_PLATFORMS for p in body.platforms):
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: invalid platforms: {body.platforms}"
        )
    if not video["video_path"] or not os.path.isfile(video["video_path"]):
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: video file not found on disk"
        )

    provider = publish.get_backend_name()
    pubs = [
        store.create_publication(video_id=video_id, platform=p, provider=provider, status="publishing")
        for p in body.platforms
    ]

    script = task_assets.read_script_json(video_id) or {}
    result = publish.cross_post_videos(
        video_paths=[video["video_path"]],
        subject=video["subject"],
        script=script.get("script", ""),
        platforms=body.platforms,
        youtube_privacy_status=body.youtube_privacy_status,
    )[0]

    for pub in pubs:
        if result.get("success"):
            transitions.mark_publication_published(store, pub["id"], url=result.get("post_id") or result.get("request_id"), result=result, actor="user")
        else:
            transitions.mark_publication_failed(store, pub["id"], error=result.get("error", "publish failed"), actor="user")

    return utils.get_response(
        200,
        {"video": store.get_video(video_id), "publications": store.list_publications(video_id)},
    )


class ScheduleRequest(BaseModel):
    platforms: list[str]
    scheduled_at: str
    provider: Optional[str] = None


@router.post("/video-library/{video_id}/schedule", response_model=None, summary="Schedule a publish for later")
def schedule_publish(request: Request, body: ScheduleRequest, video_id: str = Path(...)):
    request_id = base.get_task_id(request)
    store = _store()
    _get_video_or_404(store, request, video_id)

    if not body.platforms or any(p not in VALID_PLATFORMS for p in body.platforms):
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: invalid platforms: {body.platforms}"
        )

    created = transitions.schedule_publications(
        store, video_id,
        platforms=body.platforms,
        provider=body.provider or publish.get_backend_name(),
        scheduled_at=body.scheduled_at,
        actor="user",
    )
    return utils.get_response(200, {"video": store.get_video(video_id), "publications": created})


@router.post(
    "/video-library/{video_id}/publications/{pub_id}/cancel",
    response_model=None,
    summary="Cancel a pending scheduled/publishing publication",
)
def cancel_publication(request: Request, video_id: str = Path(...), pub_id: str = Path(...)):
    request_id = base.get_task_id(request)
    store = _store()
    _get_video_or_404(store, request, video_id)
    pub = store.get_publication(pub_id)
    if not pub or pub["video_id"] != video_id:
        raise HttpException(
            task_id=request_id, status_code=404, message=f"{request_id}: publication not found: {pub_id}"
        )
    try:
        result = transitions.cancel_publication(store, pub_id, actor="user")
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")
    return utils.get_response(200, result)


@router.post("/video-library/{video_id}/archive", response_model=None, summary="Archive a video")
def archive_video(request: Request, video_id: str = Path(...)):
    request_id = base.get_task_id(request)
    store = _store()
    _get_video_or_404(store, request, video_id)
    try:
        video = transitions.mark_archived(store, video_id, actor="user")
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")
    return utils.get_response(200, video)


@router.post("/video-library/{video_id}/restore", response_model=None, summary="Restore an archived video")
def restore_video(request: Request, video_id: str = Path(...)):
    request_id = base.get_task_id(request)
    store = _store()
    _get_video_or_404(store, request, video_id)
    try:
        video = transitions.mark_restored(store, video_id, actor="user")
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")
    return utils.get_response(200, video)


@router.post("/video-library/{video_id}/re-render", response_model=None, summary="Submit a fresh render from the original params")
def re_render(request: Request, video_id: str = Path(...)):
    from app.controllers.v1 import video as video_controller
    from app.models.schema import TaskVideoRequest

    request_id = base.get_task_id(request)
    store = _store()
    original = _get_video_or_404(store, request, video_id)

    script = task_assets.read_script_json(video_id)
    if not script or "params" not in script:
        raise HttpException(
            task_id=request_id, status_code=400,
            message=f"{request_id}: original render params not found for {video_id}",
        )

    task_request = TaskVideoRequest(**script["params"])
    response = video_controller.create_task(request, task_request, stop_at="video", source=original["source"])
    new_task_id = response.get("data", {}).get("task_id")
    if new_task_id:
        transitions.record_re_render(store, video_id, new_task_id, actor="user")
    return response


@router.post("/video-library/run-due-publications", response_model=None, summary="Manually run the due-publications scan")
def run_due_publications_endpoint(request: Request):
    from app.services.video_library_scheduler import run_due_publications

    return utils.get_response(200, {"processed": run_due_publications()})
