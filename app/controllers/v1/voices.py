import os
from typing import Optional

from fastapi import Query, Request

from app.controllers.v1.base import new_router
from app.services import voice_catalog
from app.utils import utils

router = new_router()


@router.get("/voices/servers", response_model=None, summary="List available TTS servers")
def list_tts_servers(request: Request):
    return utils.get_response(200, {"servers": voice_catalog.list_tts_servers()})


@router.get("/voices", response_model=None, summary="List voices for a TTS server")
def list_voices(
    request: Request,
    tts_server: str = Query(...),
    elevenlabs_api_key: Optional[str] = Query(default=None),
):
    voices = voice_catalog.list_voices(tts_server, elevenlabs_api_key=elevenlabs_api_key)
    return utils.get_response(200, {"voices": voices})


@router.get("/fonts", response_model=None, summary="List bundled subtitle fonts")
def list_fonts(request: Request):
    font_dir = utils.font_dir()
    fonts = sorted(
        name
        for name in os.listdir(font_dir)
        if name.lower().endswith((".ttf", ".ttc"))
    )
    return utils.get_response(200, {"fonts": fonts})


@router.get("/bgm-profiles", response_model=None, summary="List channel BGM profiles")
def list_bgm_profiles(request: Request):
    from app.services import bgm as bgm_service

    return utils.get_response(200, {"profiles": bgm_service.list_profiles()})
