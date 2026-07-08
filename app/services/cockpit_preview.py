"""Cockpit preview: generate script + terms (+ optional TTS sample) inline.

Port of webui/cockpit.py::run_preview. Unlike a render, this never touches
task_manager/state — it's a synchronous request/response operation, fast
enough (LLM + TTS calls only, no video rendering) to run inline in an HTTP
handler. See app/controllers/v1/cockpit.py::run_preview_endpoint.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.models.schema import Workspace
from app.utils import utils


class PreviewError(RuntimeError):
    """Raised when script/terms generation fails; message is user-facing."""


def _is_terms_error(terms: Any) -> bool:
    return isinstance(terms, str) and "Error: " in terms


def run_preview(
    workspace: Workspace,
    *,
    include_audio: bool,
) -> Workspace:
    from app.services import llm, voice
    from app.services.cockpit_keywords import normalized_to_workspace_keywords

    if not workspace.script.video_subject and not workspace.script.video_script:
        raise PreviewError("Video Script and Subject Cannot Both Be Empty")

    script = str(workspace.script.video_script or "").strip()
    if not script:
        script = llm.generate_script(
            video_subject=workspace.script.video_subject,
            language=workspace.script.video_language,
            paragraph_number=workspace.script.paragraph_number,
            video_script_prompt=workspace.script.video_script_prompt,
            custom_system_prompt=(
                workspace.script.custom_system_prompt
                if workspace.script.use_custom_system_prompt
                else ""
            ),
        )
    if not script or script.startswith("Error:"):
        raise PreviewError(script or "Video Generation Failed")

    amount = llm.default_terms_amount(workspace.script.match_materials_to_script)
    terms = llm.generate_terms(
        video_subject=workspace.script.video_subject,
        video_script=script,
        amount=amount,
        match_script_order=workspace.script.match_materials_to_script,
    )
    if _is_terms_error(terms):
        raise PreviewError(str(terms))

    workspace.script.video_script = script
    workspace.keywords = normalized_to_workspace_keywords(terms)

    audio_filename: str | None = None
    if include_audio and not workspace.voice.custom_audio_file:
        temp_dir = utils.storage_dir("temp", create=True)
        audio_filename = f"preview-{uuid4()}.mp3"
        audio_path = os.path.join(temp_dir, audio_filename)
        sub_maker = voice.tts(
            text=script,
            voice_name=workspace.voice.voice_name,
            voice_rate=workspace.voice.voice_rate,
            voice_file=audio_path,
            voice_volume=workspace.voice.voice_volume,
        )
        if not (sub_maker and os.path.isfile(audio_path)):
            audio_filename = None

    workspace.preview.ready = True
    workspace.preview.last_preview_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    workspace.preview.last_preview_audio_file = audio_filename
    workspace.active_step = 3

    return workspace
