"""Stage-specific configuration inspector for the production cockpit."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

import streamlit as st

from webui import cockpit


@dataclass
class InspectorCallbacks:
    get_all_fonts: Callable[[], list[str]]
    sync_chatterbox: Callable[[], None]
    detect_audio_mime: Callable[[str, bytes], str]
    default_chatterbox_base_url: str = "http://127.0.0.1:4123/v1"
    default_chatterbox_model: str = "chatterbox"
    default_chatterbox_voices: list[str] = field(default_factory=lambda: ["default-Female"])
    parse_chatterbox_voices: Callable[[Any], list[str]] | None = None
    llm_min_paragraphs: int = 1
    llm_max_paragraphs: int = 20
    llm_max_prompt: int = 500
    llm_max_system_prompt: int = 8000


def render_stage_inspector(
    step_id: str,
    runtime: dict[str, Any],
    params: Any,
    tr: Callable[[str], str],
    *,
    callbacks: InspectorCallbacks | None = None,
) -> tuple[list, Any]:
    """Render configuration controls for the active pipeline step."""
    uploaded_files: list = []
    uploaded_audio_file = None

    if callbacks is None:
        st.caption(tr("Cockpit Inspector Unavailable"))
        return uploaded_files, uploaded_audio_file

    if step_id == "script":
        render_inspector_script(params, runtime, tr, callbacks)
    elif step_id == "collector":
        uploaded_files = render_inspector_media(params, runtime, tr, callbacks)
    elif step_id == "preview":
        uploaded_audio_file = render_inspector_voice(params, runtime, tr, callbacks)
    elif step_id == "render":
        render_inspector_subtitles(params, runtime, tr, callbacks)
    elif step_id == "publish":
        render_inspector_publish(params, runtime, tr)
    elif step_id == "result":
        render_inspector_result(params, runtime, tr)

    return uploaded_files, uploaded_audio_file


def render_inspector_script(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
    callbacks: InspectorCallbacks,
) -> None:
    model = cockpit._humanize_model_label(cockpit._resolve_llm_model_label())
    cockpit._render_context_rows([(tr("Cockpit Summary Model"), model)])

    cockpit.render_title_overlay_controls(params, runtime, tr)

    params.paragraph_number = st.slider(
        tr("Script Paragraph Number"),
        min_value=callbacks.llm_min_paragraphs,
        max_value=callbacks.llm_max_paragraphs,
        value=st.session_state.get("paragraph_number_input", 1),
        key="paragraph_number_input",
    )
    params.video_script_prompt = st.text_area(
        tr("Custom Script Requirements"),
        height=80,
        max_chars=callbacks.llm_max_prompt,
        placeholder=tr("Custom Script Requirements Placeholder"),
        key="video_script_prompt",
    ).strip()

    use_custom = st.checkbox(
        tr("Use Custom System Prompt"),
        help=tr("Use Custom System Prompt Help"),
        key="use_custom_system_prompt",
    )
    if use_custom:
        params.custom_system_prompt = st.text_area(
            tr("Custom System Prompt"),
            height=120,
            max_chars=callbacks.llm_max_system_prompt,
            key="custom_system_prompt",
        ).strip()
    else:
        params.custom_system_prompt = ""

    script_mode_options = [
        (tr("Script Mode Auto"), "auto"),
        (tr("Script Mode Verbatim"), "verbatim"),
        (tr("Script Mode Polish"), "polish"),
    ]
    values = [v for _, v in script_mode_options]
    saved = st.session_state.get("script_mode", "auto")
    if saved not in values:
        saved = "auto"
    st.radio(
        tr("Script Mode"),
        options=values,
        format_func=lambda v: next(l for l, opt in script_mode_options if opt == v),
        index=values.index(saved),
        horizontal=True,
        key="script_mode",
    )
    cockpit.render_inheritance_badge("paragraph_number_input", tr)

    cockpit.render_script_stage_summary(params, runtime, tr)


def render_inspector_media(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
    callbacks: InspectorCallbacks,
) -> list:
    from app.config import config
    from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode

    uploaded_files: list = []
    video_concat_modes = [
        (tr("Sequential"), "sequential"),
        (tr("Random"), "random"),
    ]
    video_sources = [
        (tr("Collector (local cache)"), "collector"),
        (tr("Pexels"), "pexels"),
        (tr("Pixabay"), "pixabay"),
        (tr("Coverr"), "coverr"),
        (tr("Local file"), "local"),
    ]
    primary_video_sources = [
        (tr("Collector (local cache)"), "collector"),
        (tr("Pexels"), "pexels"),
        (tr("Local file"), "local"),
    ]
    primary_values = {v for _, v in primary_video_sources}
    saved_video_source_name = config.ui.get(
        "video_source",
        config.app.get("video_source", "pexels"),
    )
    if saved_video_source_name == "stock":
        saved_video_source_name = "pexels"
    card_default = (
        saved_video_source_name if saved_video_source_name in primary_values else "collector"
    )
    params.video_source = cockpit.render_option_cards(
        tr("Video Source"),
        primary_video_sources,
        card_default,
        "cockpit_video_source",
    )
    config.ui["video_source"] = params.video_source
    cockpit.render_inheritance_badge("video_source", tr)

    if params.video_source == "local":
        local_types = ["mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png"]
        uploaded_files = st.file_uploader(
            tr("Upload Local Files"),
            type=local_types + [t.upper() for t in local_types],
            accept_multiple_files=True,
        )

    saved_concat = str(config.ui.get("video_concat_mode", runtime.get("video_concat_mode", "random")))
    concat_value = cockpit.render_option_cards(
        tr("Video Concat Mode"),
        video_concat_modes,
        saved_concat,
        "cockpit_video_concat_mode",
    )
    params.video_concat_mode = VideoConcatMode(concat_value)
    config.ui["video_concat_mode"] = concat_value
    cockpit.render_inheritance_badge("video_concat_mode", tr)

    video_transition_modes = [
        (tr("None"), VideoTransitionMode.none.value),
        (tr("Shuffle"), VideoTransitionMode.shuffle.value),
        (tr("FadeIn"), VideoTransitionMode.fade_in.value),
        (tr("FadeOut"), VideoTransitionMode.fade_out.value),
        (tr("SlideIn"), VideoTransitionMode.slide_in.value),
        (tr("SlideOut"), VideoTransitionMode.slide_out.value),
    ]
    selected_index = st.selectbox(
        tr("Video Transition Mode"),
        options=range(len(video_transition_modes)),
        format_func=lambda x: video_transition_modes[x][0],
        index=0,
    )
    params.video_transition_mode = VideoTransitionMode(video_transition_modes[selected_index][1])

    video_aspect_ratios = [
        (tr("Portrait"), VideoAspect.portrait.value),
        (tr("Landscape"), VideoAspect.landscape.value),
    ]
    saved_video_aspect = config.ui.get("video_aspect", VideoAspect.portrait.value)
    if isinstance(saved_video_aspect, VideoAspect):
        saved_video_aspect = saved_video_aspect.value
    default_aspect = (
        VideoAspect.landscape.value
        if params.video_source == "coverr"
        else saved_video_aspect
    )
    params.video_aspect = VideoAspect(
        cockpit.render_option_cards(
            tr("Video Ratio"),
            video_aspect_ratios,
            default_aspect,
            f"cockpit_video_aspect_{params.video_source}",
        )
    )
    config.ui["video_aspect"] = params.video_aspect.value
    cockpit.render_inheritance_badge("video_aspect", tr)

    params.video_clip_duration = st.selectbox(
        tr("Clip Duration"), options=[2, 3, 4, 5, 6, 7, 8, 9, 10], index=1
    )
    params.video_count = st.selectbox(
        tr("Number of Videos Generated Simultaneously"),
        options=[1, 2, 3, 4, 5],
        index=0,
    )

    with st.expander(tr("Advanced Video Settings"), expanded=False):
        params.match_materials_to_script = st.checkbox(
            tr("Match Materials to Script Order"),
            help=tr("Match Materials to Script Order Help"),
            key="match_materials_to_script",
        )
        config.app["match_materials_to_script"] = params.match_materials_to_script

    return uploaded_files or []


def render_inspector_voice(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
    callbacks: InspectorCallbacks,
) -> Any:
    from app.config import config
    from app.services import bgm as bgm_service
    from app.services import voice
    from app.utils import utils
    from loguru import logger

    tts_servers = [
        (voice.NO_VOICE_NAME, tr("No Voice")),
        ("azure-tts-v1", "Azure TTS V1"),
        ("azure-tts-v2", "Azure TTS V2"),
        ("siliconflow", "SiliconFlow TTS"),
        ("gemini-tts", "Google Gemini TTS"),
        ("mimo-tts", "Xiaomi MiMo TTS"),
        ("elevenlabs", "ElevenLabs TTS"),
        ("chatterbox", "Chatterbox TTS"),
    ]
    saved_tts_server = config.ui.get("tts_server", "azure-tts-v1")
    saved_tts_server_index = next(
        (i for i, (v, _) in enumerate(tts_servers) if v == saved_tts_server),
        0,
    )
    selected_tts_server_index = st.selectbox(
        tr("TTS Servers"),
        options=range(len(tts_servers)),
        format_func=lambda x: tts_servers[x][1],
        index=saved_tts_server_index,
    )
    selected_tts_server = tts_servers[selected_tts_server_index][0]
    config.ui["tts_server"] = selected_tts_server

    filtered_voices: list[str] = []
    if selected_tts_server == voice.NO_VOICE_NAME:
        filtered_voices = [voice.NO_VOICE_NAME]
    elif selected_tts_server == "siliconflow":
        filtered_voices = voice.get_siliconflow_voices()
    elif selected_tts_server == "gemini-tts":
        filtered_voices = voice.get_gemini_voices()
    elif selected_tts_server == "mimo-tts":
        filtered_voices = voice.get_mimo_voices()
    elif selected_tts_server == "elevenlabs":
        api_key = st.session_state.get(
            "elevenlabs_api_key_input", config.elevenlabs.get("api_key", "")
        )
        cache_key = f"elevenlabs_voices_{api_key}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = voice.get_elevenlabs_voices(api_key)
        filtered_voices = st.session_state[cache_key]
    elif selected_tts_server == "chatterbox":
        callbacks.sync_chatterbox()
        filtered_voices = voice.get_chatterbox_voices()
    else:
        all_voices = voice.get_all_azure_voices(filter_locals=None)
        for v in all_voices:
            if selected_tts_server == "azure-tts-v2":
                if "V2" in v:
                    filtered_voices.append(v)
            elif "V2" not in v:
                filtered_voices.append(v)

    voice_name = ""
    if selected_tts_server == voice.NO_VOICE_NAME:
        params.voice_name = voice.NO_VOICE_NAME
        config.ui["voice_name"] = voice.NO_VOICE_NAME
    elif filtered_voices:

        def _friendly(v: str) -> str:
            if voice.is_elevenlabs_voice(v):
                parts = v.split(":", 2)
                return parts[2] if len(parts) >= 3 else v
            if voice.is_chatterbox_voice(v):
                name = v.split(":", 1)[1] if ":" in v else v
                return name.replace("-Female", "").replace("-Male", "")
            return (
                v.replace("Female", tr("Female"))
                .replace("Male", tr("Male"))
                .replace("Neural", "")
            )

        friendly_names = {v: _friendly(v) for v in filtered_voices}
        saved_voice_name = config.ui.get("voice_name", "")
        saved_voice_name_index = (
            list(friendly_names.keys()).index(saved_voice_name)
            if saved_voice_name in friendly_names
            else 0
        )
        selected_friendly = st.selectbox(
            tr("Speech Synthesis"),
            options=list(friendly_names.values()),
            index=min(saved_voice_name_index, len(friendly_names) - 1),
        )
        voice_name = list(friendly_names.keys())[
            list(friendly_names.values()).index(selected_friendly)
        ]
        params.voice_name = voice_name
        config.ui["voice_name"] = voice_name
        cockpit.render_inheritance_badge("voice_name", tr)
    else:
        st.warning(
            tr("No voices available for the selected TTS server. Please select another server.")
        )
        params.voice_name = ""
        config.ui["voice_name"] = ""

    if (
        filtered_voices
        and selected_tts_server != voice.NO_VOICE_NAME
        and st.button(tr("Play Voice"))
    ):
        if selected_tts_server == "chatterbox":
            callbacks.sync_chatterbox()
        play_content = params.video_subject or params.video_script or tr("Voice Example")
        with st.spinner(tr("Synthesizing Voice")):
            temp_dir = utils.storage_dir("temp", create=True)
            audio_file = os.path.join(temp_dir, f"tmp-voice-{uuid4()}.mp3")
            sub_maker = voice.tts(
                text=play_content,
                voice_name=voice_name or params.voice_name,
                voice_rate=params.voice_rate,
                voice_file=audio_file,
                voice_volume=params.voice_volume,
            )
            if sub_maker and os.path.exists(audio_file):
                with open(audio_file, "rb") as f:
                    audio_bytes = f.read()
                if audio_bytes:
                    st.audio(audio_bytes, format=callbacks.detect_audio_mime(audio_file, audio_bytes))
            if os.path.exists(audio_file):
                os.remove(audio_file)

    params.voice_volume = st.selectbox(
        tr("Speech Volume"),
        options=[0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0],
        index=2,
    )
    params.voice_rate = st.selectbox(
        tr("Speech Rate"),
        options=[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0],
        index=2,
    )

    custom_audio_types = ["mp3", "wav", "m4a", "aac", "flac", "ogg"]
    uploaded_audio_file = st.file_uploader(
        tr("Custom Audio File"),
        type=custom_audio_types + [t.upper() for t in custom_audio_types],
        accept_multiple_files=False,
        key="custom_audio_file_uploader",
    )

    bgm_options = [
        (tr("No Background Music"), ""),
        (tr("Random Background Music"), "random"),
        (tr("Random Background Music by Profile"), "profile_random"),
        (tr("Custom Background Music"), "custom"),
    ]
    saved_bgm_type = config.ui.get("bgm_type", "random")
    params.bgm_type = cockpit.render_option_cards(
        tr("Background Music"),
        bgm_options,
        saved_bgm_type if saved_bgm_type in {"", "random", "profile_random", "custom"} else "random",
        "cockpit_bgm_type",
    )
    config.ui["bgm_type"] = params.bgm_type
    params.bgm_file = ""
    params.bgm_profile = config.ui.get("bgm_profile", "")
    if params.bgm_type == "custom":
        custom_bgm = st.text_input(
            tr("Custom Background Music File"),
            value=config.ui.get("bgm_file", ""),
            key="custom_bgm_file_input",
        )
        config.ui["bgm_file"] = custom_bgm.strip()
        if custom_bgm:
            params.bgm_file = custom_bgm.strip()
    elif params.bgm_type == "profile_random":
        profiles = bgm_service.list_profiles()
        if profiles:
            saved_profile = config.ui.get("bgm_profile", "")
            params.bgm_profile = cockpit.render_option_cards(
                tr("Background Music Profile"),
                [(p, p) for p in profiles],
                saved_profile if saved_profile in profiles else profiles[0],
                "cockpit_bgm_profile",
            )
            config.ui["bgm_profile"] = params.bgm_profile
    params.bgm_volume = st.selectbox(
        tr("Background Music Volume"),
        options=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        index=2,
    )
    cockpit.render_inheritance_badge("bgm_type", tr)
    return uploaded_audio_file


def render_inspector_subtitles(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
    callbacks: InspectorCallbacks,
) -> None:
    cockpit.render_subtitle_controls(
        params, tr, callbacks.get_all_fonts, compact=True
    )


def render_inspector_publish(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
) -> None:
    from app.services import publish as publish_service

    platforms, _, privacy = cockpit.resolve_cockpit_publish_platforms(runtime)
    backend = publish_service.get_backend_name()
    configured = publish_service.get_active_service().is_configured()
    cockpit._render_context_rows([
        (tr("Cockpit Publish Backend"), backend),
        (tr("Cockpit Publish Platforms"), ", ".join(platforms) or "—"),
        (
            tr("Cockpit Publish Status"),
            tr("Cockpit Status Ready") if configured else tr("Cockpit Status Blocked"),
        ),
        (tr("Cockpit Publish YouTube Privacy"), privacy or "—"),
    ])
    if publish_service.get_backend_name() == "zernio":
        from app.config import config

        consent = bool(config.app.get("zernio_tiktok_consent", False))
        cockpit._render_context_rows([
            (
                tr("Cockpit Publish TikTok Consent"),
                tr("Yes") if consent else tr("No"),
            ),
        ])


def render_inspector_result(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
) -> None:
    st.caption(f"{tr('Cockpit Target Duration')}: {runtime.get('target_duration', '—')}")
    st.caption(f"{tr('Cockpit Channel Mode')}: {runtime.get('mode', 'faceless')}")
    st.caption(f"{tr('Cockpit Video Count')}: {params.video_count or 1}")
