from fastapi import Query, Request
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import WorkspacePatch
from app.services import cockpit_state, provider_readiness, workspace_store
from app.services.cockpit_preview import PreviewError
from app.utils import utils

router = new_router()


def _load_channel_runtime_or_404(request: Request, channel_slug: str) -> dict:
    request_id = base.get_task_id(request)
    try:
        return cockpit_state.build_channel_runtime(channel_slug)
    except FileNotFoundError:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: channel not found: {channel_slug}",
        )


@router.get("/cockpit/workspace", response_model=None, summary="Get (or lazily create) a channel's workspace")
def get_workspace(request: Request, channel_slug: str | None = Query(default=None)):
    seed = None
    if channel_slug:
        runtime = _load_channel_runtime_or_404(request, channel_slug)
        seed = cockpit_state.workspace_seed_from_runtime(runtime)
    workspace = workspace_store.load_workspace(channel_slug, seed=seed)
    return utils.get_response(200, workspace.model_dump(mode="json"))


@router.patch("/cockpit/workspace", response_model=None, summary="Partially update a channel's workspace")
def patch_workspace(
    request: Request,
    body: WorkspacePatch,
    channel_slug: str | None = Query(default=None),
):
    workspace = workspace_store.patch_workspace(channel_slug, body)
    if channel_slug:
        runtime = _load_channel_runtime_or_404(request, channel_slug)
        workspace.overrides = cockpit_state.detect_overrides(runtime, workspace)
        workspace = workspace_store.save_workspace(workspace)
    return utils.get_response(200, workspace.model_dump(mode="json"))


@router.post("/cockpit/workspace/reset", response_model=None, summary="Reset a workspace to channel defaults")
def reset_workspace(request: Request, channel_slug: str = Query(...)):
    runtime = _load_channel_runtime_or_404(request, channel_slug)
    seed = cockpit_state.workspace_seed_from_runtime(runtime)
    workspace = workspace_store.reset_workspace(channel_slug, seed)
    return utils.get_response(200, workspace.model_dump(mode="json"))


class RestoreFieldRequest(BaseModel):
    field_key: str


@router.post(
    "/cockpit/workspace/restore-field",
    response_model=None,
    summary="Restore one field to the channel baseline",
)
def restore_field(
    request: Request,
    body: RestoreFieldRequest,
    channel_slug: str = Query(...),
):
    request_id = base.get_task_id(request)
    runtime = _load_channel_runtime_or_404(request, channel_slug)
    if body.field_key not in cockpit_state.RUNTIME_FIELD_MAP:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: unknown field_key: {body.field_key}",
        )
    if body.field_key not in runtime:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: field not present on channel baseline: {body.field_key}",
        )

    group, field = cockpit_state.RUNTIME_FIELD_MAP[body.field_key]
    patch = WorkspacePatch(**{group: {field: runtime[body.field_key]}})
    workspace = workspace_store.patch_workspace(channel_slug, patch)
    workspace.preview.ready = False
    workspace.overrides = cockpit_state.detect_overrides(runtime, workspace)
    workspace = workspace_store.save_workspace(workspace)
    return utils.get_response(200, workspace.model_dump(mode="json"))


@router.get(
    "/cockpit/workspace/steps",
    response_model=None,
    summary="Per-step done/active/pending status for the wizard nav",
)
def get_workspace_steps(request: Request, channel_slug: str | None = Query(default=None)):
    workspace = workspace_store.load_workspace(channel_slug)
    states = cockpit_state.compute_pipeline_step_states(workspace)
    blockers = provider_readiness.list_render_blockers(
        workspace.media.video_source, workspace.voice.voice_name
    )
    return utils.get_response(
        200,
        {"states": states, "step_ids": list(cockpit_state.STEP_IDS), "blockers": blockers},
    )


class RunPreviewRequest(BaseModel):
    include_audio: bool = False


@router.post("/cockpit/preview", response_model=None, summary="Generate script/terms (+ optional TTS sample)")
def run_preview_endpoint(
    request: Request,
    body: RunPreviewRequest,
    channel_slug: str | None = Query(default=None),
):
    from app.services.cockpit_preview import run_preview

    request_id = base.get_task_id(request)
    workspace = workspace_store.load_workspace(channel_slug)
    try:
        workspace = run_preview(workspace, include_audio=body.include_audio)
    except PreviewError as exc:
        raise HttpException(task_id=request_id, status_code=400, message=f"{request_id}: {exc}")

    workspace = workspace_store.save_workspace(workspace)
    payload = workspace.model_dump(mode="json")
    if workspace.preview.last_preview_audio_file:
        payload["preview_audio_url"] = (
            f"/api/v1/cockpit/preview-audio/{workspace.preview.last_preview_audio_file}"
        )
    return utils.get_response(200, payload)


@router.get(
    "/cockpit/preview-audio/{filename}",
    summary="Stream a preview TTS sample generated by /cockpit/preview",
)
def get_preview_audio(request: Request, filename: str):
    import os

    from fastapi.responses import FileResponse

    request_id = base.get_task_id(request)
    if not filename.startswith("preview-") or not filename.endswith(".mp3") or "/" in filename:
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: invalid filename"
        )
    temp_dir = utils.storage_dir("temp", create=True)
    path = os.path.join(temp_dir, filename)
    if not os.path.isfile(path):
        raise HttpException(
            task_id=request_id, status_code=404, message=f"{request_id}: preview audio not found"
        )
    return FileResponse(path=path, media_type="audio/mp3")


@router.get(
    "/cockpit/providers",
    response_model=None,
    summary="Aggregated LLM/collector/TTS/FFmpeg/BGM readiness",
)
def get_providers(
    request: Request,
    video_source: str = Query(default="pexels"),
    voice_name: str = Query(default=""),
):
    return utils.get_response(200, provider_readiness.all_readiness(video_source, voice_name))


@router.get("/cockpit/runtime-limits", response_model=None, summary="Runtime caps + generation lock status")
def get_runtime_limits(request: Request):
    from app.services import runtime_limits

    limits = runtime_limits.get_runtime_limits()
    lock = runtime_limits.generation_lock_status()
    return utils.get_response(
        200,
        {
            "max_threads": limits.max_threads,
            "max_remote_video_mb": limits.max_remote_video_mb,
            "max_downloads_per_task": limits.max_downloads_per_task,
            "generation_lock_ttl_seconds": limits.generation_lock_ttl_seconds,
            "low_memory_mode": limits.low_memory_mode,
            "lock": lock,
        },
    )


class ClearLockRequest(BaseModel):
    force: bool = False


@router.post(
    "/cockpit/runtime-limits/clear-lock",
    response_model=None,
    summary="Clear a stale (or, with force, any) generation lock",
)
def clear_generation_lock(request: Request, body: ClearLockRequest):
    from app.services import runtime_limits

    cleared = runtime_limits.clear_stale_generation_lock(force=body.force)
    return utils.get_response(200, {"cleared": cleared})
