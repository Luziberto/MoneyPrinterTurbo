"""TTS voice listing for the cockpit API.

Port of the per-provider voice-listing logic embedded inline in
webui/cockpit_inspector.py's render_inspector_voice (there's no existing
standalone function to extract here -- this is new logic, not a 1:1 port,
flagged as such in the migration plan).
"""

from __future__ import annotations

from app.config import config
from app.services import voice

TTS_SERVERS = (
    (voice.NO_VOICE_NAME, "No Voice"),
    ("azure-tts-v1", "Azure TTS V1"),
    ("azure-tts-v2", "Azure TTS V2"),
    ("siliconflow", "SiliconFlow TTS"),
    ("gemini-tts", "Google Gemini TTS"),
    ("mimo-tts", "Xiaomi MiMo TTS"),
    ("elevenlabs", "ElevenLabs TTS"),
    ("chatterbox", "Chatterbox TTS"),
)


def list_tts_servers() -> list[dict[str, str]]:
    return [{"id": server_id, "label": label} for server_id, label in TTS_SERVERS]


def _friendly_name(raw: str) -> str:
    if voice.is_elevenlabs_voice(raw):
        parts = raw.split(":", 2)
        return parts[2] if len(parts) >= 3 else raw
    if voice.is_chatterbox_voice(raw):
        name = raw.split(":", 1)[1] if ":" in raw else raw
        return name.replace("-Female", "").replace("-Male", "")
    return raw.replace("Neural", "")


def list_voices(tts_server: str, *, elevenlabs_api_key: str | None = None) -> list[dict[str, str]]:
    if tts_server == voice.NO_VOICE_NAME:
        raw_voices = [voice.NO_VOICE_NAME]
    elif tts_server == "siliconflow":
        raw_voices = voice.get_siliconflow_voices()
    elif tts_server == "gemini-tts":
        raw_voices = voice.get_gemini_voices()
    elif tts_server == "mimo-tts":
        raw_voices = voice.get_mimo_voices()
    elif tts_server == "elevenlabs":
        api_key = elevenlabs_api_key or config.elevenlabs.get("api_key", "")
        raw_voices = voice.get_elevenlabs_voices(api_key)
    elif tts_server == "chatterbox":
        raw_voices = voice.get_chatterbox_voices()
    elif tts_server in ("azure-tts-v1", "azure-tts-v2"):
        all_voices = voice.get_all_azure_voices(filter_locals=None)
        raw_voices = [
            v
            for v in all_voices
            if ("V2" in v) == (tts_server == "azure-tts-v2")
        ]
    else:
        raw_voices = []

    return [{"name": v, "label": _friendly_name(v)} for v in raw_voices]
