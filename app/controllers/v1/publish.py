from typing import Optional

from fastapi import Query, Request
from pydantic import BaseModel

from app.controllers.v1.base import new_router
from app.services import publish, workspace_store
from app.utils import utils

router = new_router()


@router.get("/publish/status", response_model=None, summary="Publish backend readiness")
def get_publish_status(request: Request):
    backend_name = publish.get_backend_name()
    service = publish.get_active_service()
    return utils.get_response(
        200,
        {
            "backend": backend_name,
            "configured": service.is_configured(),
            "platforms": list(service.platforms),
            "auto_upload": service.auto_upload,
            "youtube_privacy_status": service.youtube_privacy_status,
        },
    )


class PublishRequest(BaseModel):
    video_paths: list[str]
    subject: str
    script: str = ""
    language: str = ""
    platforms: Optional[list[str]] = None
    youtube_privacy_status: Optional[str] = None


@router.post("/publish", response_model=None, summary="Cross-post rendered videos to social platforms")
def create_publish(
    request: Request,
    body: PublishRequest,
    channel_slug: Optional[str] = Query(default=None),
):
    results = publish.cross_post_videos(
        video_paths=body.video_paths,
        subject=body.subject,
        script=body.script,
        language=body.language,
        platforms=body.platforms,
        youtube_privacy_status=body.youtube_privacy_status,
    )

    if channel_slug:
        workspace = workspace_store.load_workspace(channel_slug)
        workspace.publish.last_results = results
        workspace.publish.done = True
        workspace_store.save_workspace(workspace)

    return utils.get_response(200, {"results": results})
