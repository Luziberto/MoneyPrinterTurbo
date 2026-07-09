from typing import Optional

from fastapi import File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import (
    ChannelConfigResponse,
    ChannelCreateBody,
    ChannelSummary,
    ChannelUpdateBody,
    WorkspacePatch,
)
from app.services import cockpit_state, workspace_store
from app.utils import utils

router = new_router()


def _load_channel_or_404(request: Request, slug: str) -> dict:
    request_id = base.get_task_id(request)
    cockpit_state.ensure_pipeline_path()
    from lib.channel import load_channel

    try:
        return load_channel(slug)
    except FileNotFoundError:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: channel not found: {slug}",
        )


def _topic_store():
    cockpit_state.ensure_pipeline_path()
    from lib.topic_store import TopicStore

    return TopicStore()


def _channel_summary(slug: str, channel: dict) -> dict:
    from lib.channel import has_avatar

    avatar_url = f"/api/v1/channels/{slug}/avatar" if has_avatar(slug) else None
    try:
        videos_per_day = int(channel.get("videos_per_day", 1) or 1)
    except (TypeError, ValueError):
        videos_per_day = 1
    return ChannelSummary(
        slug=slug,
        name=str(channel.get("name", slug) or slug),
        niche=str(channel.get("niche", "") or ""),
        mode=str(channel.get("mode", "faceless") or "faceless"),
        video_source=str(channel.get("video_source", "pexels") or "pexels"),
        avatar_url=avatar_url,
        videos_per_day=max(1, videos_per_day),
    ).model_dump()


@router.get("/channels", response_model=None, summary="List pipeline channels")
def list_channels(request: Request):
    cockpit_state.ensure_pipeline_path()
    from lib.channel import list_channels as _list_channels

    summaries = []
    for slug in _list_channels():
        channel = _load_channel_or_404(request, slug)
        summaries.append(_channel_summary(slug, channel))
    return utils.get_response(200, {"channels": summaries})


@router.get("/channels/{slug}", response_model=None, summary="Get a channel's full config + runtime view")
def get_channel(request: Request, slug: str):
    channel = _load_channel_or_404(request, slug)
    runtime = cockpit_state.build_channel_runtime(slug)
    response = ChannelConfigResponse(slug=slug, config=channel, runtime=runtime)
    return utils.get_response(200, response.model_dump(mode="json"))


@router.post("/channels", response_model=None, summary="Create a pipeline channel")
def create_channel(request: Request, body: ChannelCreateBody):
    request_id = base.get_task_id(request)
    cockpit_state.ensure_pipeline_path()
    from lib.channel import create_channel as _create_channel

    try:
        channel = _create_channel(body.slug, body.name, body.niche)
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")
    except FileExistsError as exc:
        raise HttpException(task_id=request_id, status_code=409, message=f"{request_id}: {exc}")

    slug = str(channel.get("slug") or body.slug)
    return utils.get_response(200, _channel_summary(slug, channel))


@router.put("/channels/{slug}", response_model=None, summary="Update a channel's configuration")
def update_channel(request: Request, slug: str, body: ChannelUpdateBody):
    request_id = base.get_task_id(request)
    cockpit_state.ensure_pipeline_path()
    from lib.channel import save_channel_config

    _load_channel_or_404(request, slug)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        channel = _load_channel_or_404(request, slug)
        return utils.get_response(200, _channel_summary(slug, channel))

    try:
        channel = save_channel_config(slug, updates)
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")

    return utils.get_response(200, _channel_summary(slug, channel))


@router.delete("/channels/{slug}", response_model=None, summary="Delete a pipeline channel")
def delete_channel(request: Request, slug: str):
    request_id = base.get_task_id(request)
    cockpit_state.ensure_pipeline_path()
    from lib.channel import delete_channel as _delete_channel

    _load_channel_or_404(request, slug)
    try:
        _delete_channel(slug)
    except FileNotFoundError as exc:
        raise HttpException(task_id=request_id, status_code=404, message=f"{request_id}: {exc}")
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")

    return utils.get_response(200, {"deleted": True, "slug": slug})


@router.get("/channels/{slug}/avatar", response_model=None, summary="Get a channel avatar image")
def get_channel_avatar(request: Request, slug: str):
    request_id = base.get_task_id(request)
    _load_channel_or_404(request, slug)
    from lib.channel import channel_avatar_path
    avatar_path = channel_avatar_path(slug)
    if avatar_path is None:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: avatar not found for channel: {slug}",
        )
    media_type = "image/png"
    if avatar_path.suffix.lower() in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    elif avatar_path.suffix.lower() == ".webp":
        media_type = "image/webp"
    return FileResponse(avatar_path, media_type=media_type)


@router.post("/channels/{slug}/avatar", response_model=None, summary="Upload a channel avatar image")
def upload_channel_avatar(request: Request, slug: str, file: UploadFile = File(...)):
    request_id = base.get_task_id(request)
    _load_channel_or_404(request, slug)
    from lib.channel import save_channel_avatar
    content = file.file.read()
    if not content:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: empty avatar upload",
        )
    try:
        save_channel_avatar(slug, content, file.filename or "avatar.png")
    except ValueError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")

    return utils.get_response(
        200,
        {
            "slug": slug,
            "avatar_url": f"/api/v1/channels/{slug}/avatar",
        },
    )


@router.get("/channels/{slug}/topics", response_model=None, summary="List a channel's topic queue")
def list_topics(request: Request, slug: str, status: Optional[str] = Query(default=None)):
    _load_channel_or_404(request, slug)
    store = _topic_store()
    topics = store.list_topics(slug)
    if status and status != "all":
        topics = [t for t in topics if t.get("status") == status]
    counts = store.count_by_status(slug)
    return utils.get_response(200, {"topics": topics, "counts": counts})


@router.post(
    "/channels/{slug}/topics/{topic_uid}/load-into-workspace",
    response_model=None,
    summary="Load a queued topic's subject into the channel's workspace",
)
def load_topic_into_workspace(request: Request, slug: str, topic_uid: str):
    request_id = base.get_task_id(request)
    _load_channel_or_404(request, slug)
    store = _topic_store()
    topic = next((t for t in store.list_topics(slug) if t.get("uid") == topic_uid), None)
    if topic is None:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: topic not found: {topic_uid}",
        )

    patch = WorkspacePatch(script={"video_subject": topic.get("topic", "")})
    workspace = workspace_store.patch_workspace(slug, patch)
    return utils.get_response(
        200,
        {
            "workspace": workspace.model_dump(mode="json"),
            "topic": topic,
        },
    )


class TopicStatusUpdate(BaseModel):
    status: str
    task_id: Optional[str] = None
    video_path: Optional[str] = None
    approved: Optional[bool] = None


@router.patch(
    "/channels/{slug}/topics/{topic_uid}",
    response_model=None,
    summary="Update a queued topic's status",
)
def update_topic(request: Request, slug: str, topic_uid: str, body: TopicStatusUpdate):
    from lib.topics import VALID_STATUSES

    request_id = base.get_task_id(request)
    _load_channel_or_404(request, slug)
    store = _topic_store()
    topic = next((t for t in store.list_topics(slug) if t.get("uid") == topic_uid), None)
    if topic is None:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: topic not found: {topic_uid}",
        )
    if body.status not in VALID_STATUSES:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: invalid status: {body.status}",
        )

    topic["status"] = body.status
    if body.task_id is not None:
        topic["task_id"] = body.task_id
    if body.video_path is not None:
        topic["video_path"] = body.video_path
    if body.approved is not None:
        topic["approved"] = body.approved
    store.update_topic(slug, topic)
    return utils.get_response(200, topic)
