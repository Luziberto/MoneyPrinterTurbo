"""Provider readiness checks for the cockpit API.

Port of webui/cockpit.py's _llm_readiness / _collector_readiness /
_tts_readiness / _ffmpeg_readiness / _bgm_readiness / list_render_blockers.

Streamlit's version returns translated strings and compares them to detect
blocked/skipped status; this version returns plain status literals
("ready" | "blocked" | "skipped") plus a `detail` value. For blocked/skipped
cases, `detail` is one of webui/i18n's existing key strings (untranslated —
the Vue client resolves it via GET /api/v1/i18n/{locale}, see Phase 5). For
ready cases, `detail` is plain informational text (provider name, model, etc),
not meant for translation.
"""

from __future__ import annotations

import os
from typing import Any, TypedDict


class ReadinessResult(TypedDict):
    status: str  # "ready" | "blocked" | "skipped"
    detail: str


def _ready(detail: str) -> ReadinessResult:
    return {"status": "ready", "detail": detail}


def _blocked(detail_key: str) -> ReadinessResult:
    return {"status": "blocked", "detail": detail_key}


def _skipped(detail_key: str) -> ReadinessResult:
    return {"status": "skipped", "detail": detail_key}


def llm_readiness() -> ReadinessResult:
    from app.config import config

    provider = str(config.app.get("llm_provider", "") or "").strip().lower()
    if not provider:
        return _blocked("Cockpit LLM Missing Provider")

    if provider == "litellm":
        model = str(config.app.get("litellm_model_name", "") or "").strip()
        if model:
            return _ready(provider)
        return _blocked("Cockpit LLM Missing Model")

    if provider == "anthropic":
        model = str(config.app.get("anthropic_model_name", "") or "").strip()
        api_key = str(
            config.app.get("anthropic_api_key")
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        ).strip()
        if not model:
            return _blocked("Cockpit LLM Missing Model")
        if api_key:
            return _ready(provider)
        return _blocked("Cockpit LLM Missing Key")

    if provider == "bedrock":
        model = str(config.app.get("bedrock_model_name", "") or "").strip()
        region = str(config.app.get("bedrock_region", "") or "").strip()
        if not model:
            return _blocked("Cockpit LLM Missing Model")
        if not region:
            return _blocked("Cockpit LLM Missing Region")

        from app.services.llm import (
            is_bedrock_mantle_responses_model,
            is_valid_bedrock_bearer_token,
            looks_like_aws_access_key_id,
            looks_like_bedrock_iam_username,
        )

        if is_bedrock_mantle_responses_model(model):
            mantle_regions = {"us-east-2", "us-west-2"}
            if region not in mantle_regions:
                return _blocked("Cockpit Bedrock Mantle Region")

        bedrock_key = str(
            config.app.get("bedrock_api_key")
            or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            or ""
        ).strip()
        if bedrock_key:
            if looks_like_bedrock_iam_username(bedrock_key):
                return _blocked("Cockpit Bedrock Key IAM Username")
            if looks_like_aws_access_key_id(bedrock_key):
                return _blocked("Cockpit Bedrock Key Wrong Field")
            if not is_valid_bedrock_bearer_token(bedrock_key):
                return _blocked("Cockpit Bedrock Key Invalid Prefix")
            return _ready(provider)

        if is_bedrock_mantle_responses_model(model):
            return _blocked("Cockpit Bedrock Mantle Key Required")

        has_config_creds = bool(
            config.app.get("bedrock_aws_access_key_id")
            and config.app.get("bedrock_aws_secret_access_key")
        )
        if has_config_creds or os.environ.get("AWS_ACCESS_KEY_ID"):
            return _ready(provider)
        return _ready("Cockpit LLM IAM Role")

    key_field = f"{provider}_api_key"
    api_key = config.app.get(key_field) or config.app.get("api_key")
    if provider in {"ollama", "g4f"}:
        return _ready(provider)
    if api_key:
        return _ready(provider)
    return _blocked("Cockpit LLM Missing Key")


def collector_readiness(video_source: str) -> ReadinessResult:
    if video_source != "collector":
        return _skipped("Cockpit Collector Not Selected")

    from app.config import config
    from app.services import collector_client

    base_url = str(config.app.get("collector_base_url", "") or "").strip()
    if not base_url:
        return _blocked("Cockpit Collector No URL")

    try:
        if collector_client.check_collector_health():
            return _ready(base_url)
    except Exception as exc:
        return _blocked(str(exc)[:80])
    return _blocked("Cockpit Collector Offline")


def tts_readiness(voice_name: str) -> ReadinessResult:
    from app.services import voice

    if not voice_name or voice.is_no_voice(voice_name):
        return _blocked("Cockpit TTS No Voice")
    return _ready(voice_name)


def ffmpeg_readiness() -> ReadinessResult:
    from app.services.video import get_ffmpeg_binary

    binary = get_ffmpeg_binary()
    if binary and os.path.isfile(binary):
        return _ready(os.path.basename(binary))
    if binary:
        return _ready(binary)
    return _blocked("Cockpit FFmpeg Missing")


def bgm_readiness() -> ReadinessResult:
    from app.services import bgm as bgm_service

    profiles = bgm_service.list_profiles()
    if profiles:
        return _ready(f"{len(profiles)} profiles")
    return _skipped("Cockpit BGM No Profiles")


def all_readiness(video_source: str, voice_name: str) -> dict[str, ReadinessResult]:
    return {
        "llm": llm_readiness(),
        "collector": collector_readiness(video_source),
        "tts": tts_readiness(voice_name),
        "ffmpeg": ffmpeg_readiness(),
        "bgm": bgm_readiness(),
    }


def list_render_blockers(video_source: str, voice_name: str) -> list[dict[str, str]]:
    """Return actionable blockers: [{provider, detail}] for anything status=="blocked"."""
    checks = all_readiness(video_source, voice_name)
    blockers = []
    for provider, result in checks.items():
        if result["status"] == "blocked":
            blockers.append({"provider": provider, "detail": result["detail"]})
    return blockers
