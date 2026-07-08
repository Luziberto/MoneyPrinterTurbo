from fastapi import Query, Request
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import WorkspacePatch
from app.services import cockpit_state, workspace_store
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
    return utils.get_response(200, {"states": states, "step_ids": list(cockpit_state.STEP_IDS)})
