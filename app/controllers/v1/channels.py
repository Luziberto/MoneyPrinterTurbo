from typing import Optional

from fastapi import Query, Request
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import ChannelConfigResponse, ChannelSummary, WorkspacePatch
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


@router.get("/channels", response_model=None, summary="List pipeline channels")
def list_channels(request: Request):
    cockpit_state.ensure_pipeline_path()
    from lib.channel import list_channels as _list_channels

    summaries = []
    for slug in _list_channels():
        channel = _load_channel_or_404(request, slug)
        summaries.append(
            ChannelSummary(
                slug=slug,
                name=str(channel.get("name", slug) or slug),
                niche=str(channel.get("niche", "") or ""),
                mode=str(channel.get("mode", "faceless") or "faceless"),
                video_source=str(channel.get("video_source", "pexels") or "pexels"),
            ).model_dump()
        )
    return utils.get_response(200, {"channels": summaries})


@router.get("/channels/{slug}", response_model=None, summary="Get a channel's full config + runtime view")
def get_channel(request: Request, slug: str):
    channel = _load_channel_or_404(request, slug)
    runtime = cockpit_state.build_channel_runtime(slug)
    response = ChannelConfigResponse(slug=slug, config=channel, runtime=runtime)
    return utils.get_response(200, response.model_dump(mode="json"))


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
