from typing import Optional
from uuid import uuid4

from fastapi import Query, Request, Response
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import CollectorJobRequest, CollectorKeyword
from app.services import collector_client, workspace_store
from app.utils import utils

router = new_router()


def _snapshot_from_job_result(job) -> dict:
    payload = job.model_dump()
    reused = int(payload.get("local_reused") or 0)
    downloads = int(payload.get("new_downloads") or 0)
    total = reused + downloads
    payload["cache_hit_pct"] = round((reused / total) * 100) if total else None
    return payload


@router.get("/collector/health", response_model=None, summary="Collector service health check")
def collector_health(request: Request):
    healthy = collector_client.check_collector_health()
    return utils.get_response(200, {"healthy": healthy})


@router.get("/collector/dashboard", response_model=None, summary="Collector dashboard stats")
def collector_dashboard(request: Request):
    return utils.get_response(200, collector_client.fetch_collector_dashboard())


@router.get("/collector/search", response_model=None, summary="Search cached collector clips")
def collector_search(request: Request, query: str = Query(...), limit: Optional[int] = Query(default=None)):
    hits = collector_client.search_collector_clips(query, limit)
    return utils.get_response(200, {"hits": hits})


class CreateCollectorJobRequest(BaseModel):
    keywords: list[CollectorKeyword]
    target_clips: int = 25
    min_acceptable_clips: int = 20
    channel_slug: Optional[str] = None


@router.post("/collector/jobs", summary="Create a collector job (returns immediately, poll for status)")
def create_collector_job(request: Request, body: CreateCollectorJobRequest, response: Response):
    request_id = base.get_task_id(request)
    if not body.keywords:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: keywords must not be empty",
        )

    job_request = CollectorJobRequest(
        client_task_id=f"cockpit-{uuid4()}",
        keywords=body.keywords,
        target_clips=body.target_clips,
        min_acceptable_clips=body.min_acceptable_clips,
    )
    try:
        job = collector_client.create_stock_job(job_request)
    except collector_client.CollectorError as exc:
        raise HttpException(
            task_id=request_id,
            status_code=502,
            message=f"{request_id}: {exc}",
        )

    response.status_code = 202
    return utils.get_response(202, job.model_dump())


@router.get("/collector/jobs/{job_id}", response_model=None, summary="Poll a collector job's status")
def get_collector_job(request: Request, job_id: str, channel_slug: Optional[str] = Query(default=None)):
    request_id = base.get_task_id(request)
    try:
        job = collector_client.get_stock_job(job_id)
    except collector_client.CollectorError as exc:
        raise HttpException(
            task_id=request_id,
            status_code=502,
            message=f"{request_id}: {exc}",
        )

    snapshot = _snapshot_from_job_result(job)
    if channel_slug and job.status == "ready":
        workspace = workspace_store.load_workspace(channel_slug)
        workspace.media.last_collector_job = snapshot
        workspace.media.video_clips = job.selected_clips or None
        workspace_store.save_workspace(workspace)

    return utils.get_response(200, snapshot)
