from typing import Optional

from fastapi import Request
from pydantic import BaseModel

from app.config import config
from app.controllers.v1.base import new_router
from app.services import config_masking
from app.utils import utils

router = new_router()

_SECTIONS = ("app", "ui", "azure", "siliconflow", "elevenlabs", "chatterbox")


@router.get(
    "/config",
    response_model=None,
    summary="Redacted snapshot of provider/UI config (config.toml sections)",
)
def get_config(request: Request):
    return utils.get_response(
        200,
        {section: config_masking.mask_section(getattr(config, section)) for section in _SECTIONS},
    )


class ConfigPatchRequest(BaseModel):
    app: Optional[dict] = None
    ui: Optional[dict] = None
    azure: Optional[dict] = None
    siliconflow: Optional[dict] = None
    elevenlabs: Optional[dict] = None
    chatterbox: Optional[dict] = None


@router.put(
    "/config",
    response_model=None,
    summary="Partially update config.toml. Unchanged masked secrets are not overwritten.",
)
def put_config(request: Request, body: ConfigPatchRequest):
    for section in _SECTIONS:
        patch = getattr(body, section)
        if patch:
            config_masking.apply_section_patch(getattr(config, section), patch)
    config.save_config()
    return utils.get_response(
        200,
        {section: config_masking.mask_section(getattr(config, section)) for section in _SECTIONS},
    )
