"""Operator cockpit helpers for the Streamlit WebUI."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT_DIR / "pipeline"


def ensure_pipeline_path() -> None:
    pipeline_path = str(PIPELINE_DIR)
    if pipeline_path not in sys.path:
        sys.path.insert(0, pipeline_path)


def list_available_channels() -> list[str]:
    ensure_pipeline_path()
    from lib.channel import list_channels

    return list_channels()


def load_channel_config(slug: str) -> dict[str, Any]:
    ensure_pipeline_path()
    from lib.channel import load_channel

    return load_channel(slug)


def apply_channel_defaults(slug: str) -> None:
    """Load channel.json defaults into Streamlit session state and config.ui."""
    channel = load_channel_config(slug)
    st.session_state["active_channel"] = slug
    st.session_state["preview_ready"] = False

    niche = str(channel.get("niche", "")).strip()
    if niche and not st.session_state.get("video_subject"):
        st.session_state["video_subject"] = niche

    st.session_state["paragraph_number_input"] = int(
        channel.get("paragraph_number", 1) or 1
    )
    st.session_state["match_materials_to_script"] = bool(
        channel.get("match_materials_to_script", False)
    )
    st.session_state["video_script_prompt"] = str(
        channel.get("video_script_prompt", "") or ""
    ).strip()

    config_ui_keys = {
        "video_source": channel.get("video_source", "collector"),
        "bgm_type": channel.get("bgm_type", "random"),
        "bgm_profile": channel.get("bgm_profile", ""),
        "font_name": channel.get("font_name", "Roboto-Bold.ttf"),
        "font_size": channel.get("font_size", 55),
        "subtitle_position": channel.get("subtitle_position", "bottom"),
        "text_fore_color": channel.get("text_fore_color", "#FFFFFF"),
    }
    from app.config import config

    for key, value in config_ui_keys.items():
        if value is not None and value != "":
            config.ui[key] = value

    voice_name = str(channel.get("voice_name", "") or "").strip()
    if voice_name:
        config.ui["voice_name"] = voice_name

    aspect = str(channel.get("video_aspect", "") or "").strip()
    if aspect:
        config.ui["video_aspect"] = aspect


def render_channel_toolbar(
    channels: list[str],
    tr: Callable[[str], str],
) -> str | None:
    """Channel selector row shown above main tabs."""
    from app.config import config

    if "active_channel" not in st.session_state:
        saved = config.ui.get("active_channel", "")
        st.session_state["active_channel"] = (
            saved if saved in channels else (channels[0] if channels else "")
        )

    if not channels:
        st.caption(tr("Cockpit No Channels"))
        return None

    col_channel, col_apply, col_info = st.columns([2, 1, 2])
    with col_channel:
        index = (
            channels.index(st.session_state["active_channel"])
            if st.session_state["active_channel"] in channels
            else 0
        )
        selected = st.selectbox(
            tr("Cockpit Active Channel"),
            options=channels,
            index=index,
            key="cockpit_channel_select",
        )
    with col_apply:
        st.write("")
        if st.button(tr("Cockpit Apply Channel Defaults"), use_container_width=True):
            apply_channel_defaults(selected)
            config.ui["active_channel"] = selected
            st.session_state["active_channel"] = selected
            st.toast(tr("Cockpit Channel Applied"))
            st.rerun()
    with col_info:
        if selected:
            try:
                channel = load_channel_config(selected)
                st.caption(
                    f"**{channel.get('name', selected)}** · "
                    f"{channel.get('video_source', '—')} · "
                    f"{channel.get('target_duration', '—')}"
                )
            except FileNotFoundError:
                st.caption(selected)

    st.session_state["active_channel"] = selected
    config.ui["active_channel"] = selected
    return selected


def _llm_readiness(tr: Callable[[str], str]) -> tuple[str, str]:
    from app.config import config

    provider = str(config.app.get("llm_provider", "") or "").strip().lower()
    if not provider:
        return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Provider")

    key_field = f"{provider}_api_key"
    api_key = config.app.get(key_field) or config.app.get("api_key")
    if provider in {"ollama", "g4f"}:
        return tr("Cockpit Status Ready"), provider
    if api_key:
        return tr("Cockpit Status Ready"), provider
    return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Key")


def _collector_readiness(
    video_source: str,
    tr: Callable[[str], str],
) -> tuple[str, str]:
    if video_source != "collector":
        return tr("Cockpit Status Skipped"), tr("Cockpit Collector Not Selected")

    from app.config import config
    from app.services import collector_client

    base_url = str(config.app.get("collector_base_url", "") or "").strip()
    if not base_url:
        return tr("Cockpit Status Blocked"), tr("Cockpit Collector No URL")

    try:
        if collector_client.check_collector_health():
            return tr("Cockpit Status Ready"), base_url
    except Exception as exc:
        return tr("Cockpit Status Blocked"), str(exc)[:80]
    return tr("Cockpit Status Blocked"), tr("Cockpit Collector Offline")


def _tts_readiness(
    voice_name: str,
    tr: Callable[[str], str],
) -> tuple[str, str]:
    from app.services import voice

    if not voice_name or voice.is_no_voice(voice_name):
        return tr("Cockpit Status Blocked"), tr("Cockpit TTS No Voice")
    return tr("Cockpit Status Ready"), voice_name


def _ffmpeg_readiness(tr: Callable[[str], str]) -> tuple[str, str]:
    from app.services.video import get_ffmpeg_binary

    binary = get_ffmpeg_binary()
    if binary and os.path.isfile(binary):
        return tr("Cockpit Status Ready"), os.path.basename(binary)
    if binary:
        return tr("Cockpit Status Ready"), binary
    return tr("Cockpit Status Blocked"), tr("Cockpit FFmpeg Missing")


def _bgm_readiness(tr: Callable[[str], str]) -> tuple[str, str]:
    from app.services import bgm as bgm_service

    profiles = bgm_service.list_profiles()
    if profiles:
        return tr("Cockpit Status Ready"), f"{len(profiles)} profiles"
    return tr("Cockpit Status Skipped"), tr("Cockpit BGM No Profiles")


def render_provider_center(
    video_source: str,
    voice_name: str,
    tr: Callable[[str], str],
) -> None:
    """Readiness grid inspired by Cenara provider center."""
    checks = [
        (tr("Cockpit Provider LLM"), *_llm_readiness(tr)),
        (tr("Cockpit Provider Collector"), *_collector_readiness(video_source, tr)),
        (tr("Cockpit Provider TTS"), *_tts_readiness(voice_name, tr)),
        (tr("Cockpit Provider FFmpeg"), *_ffmpeg_readiness(tr)),
        (tr("Cockpit Provider BGM"), *_bgm_readiness(tr)),
    ]
    with st.expander(tr("Cockpit Provider Center"), expanded=True):
        cols = st.columns(len(checks))
        for index, (label, status, detail) in enumerate(checks):
            with cols[index % len(cols)]:
                st.metric(label, status, detail)


def render_channels_tab(
    channels: list[str],
    tr: Callable[[str], str],
) -> None:
    ensure_pipeline_path()
    from lib.topic_store import TopicStore

    if not channels:
        st.info(tr("Cockpit No Channels"))
        return

    active = st.session_state.get("active_channel") or channels[0]
    if active not in channels:
        active = channels[0]

    try:
        channel = load_channel_config(active)
    except FileNotFoundError:
        st.error(tr("Cockpit Channel Not Found"))
        return

    st.subheader(channel.get("name", active))
    st.caption(
        f"{channel.get('niche', '')} · {channel.get('videos_per_day', '—')} vídeos/dia"
    )

    store = TopicStore()
    topics = store.list_topics(active)
    counts = store.count_by_status(active)

    metric_cols = st.columns(len(counts) or 1)
    for index, (status, count) in enumerate(sorted(counts.items())):
        with metric_cols[index % len(metric_cols)]:
            st.metric(status, count)

    if not topics:
        st.info(tr("Cockpit No Topics"))
        return

    pending = [topic for topic in topics if topic.get("status") == "pending"]
    st.write(f"**{tr('Cockpit Pending Topics')}** ({len(pending)})")

    for topic in pending[:25]:
        cols = st.columns([1, 4, 1])
        topic_id = topic.get("id")
        with cols[0]:
            st.write(f"#{topic_id}")
        with cols[1]:
            st.write(topic.get("topic", ""))
            profiles = topic.get("music_profiles") or []
            if profiles:
                st.caption(", ".join(profiles))
        with cols[2]:
            if st.button(
                tr("Cockpit Load Topic"),
                key=f"load_topic_{topic.get('uid', topic_id)}",
            ):
                st.session_state["video_subject"] = topic.get("topic", "")
                st.session_state["preview_ready"] = False
                st.session_state["loaded_topic_uid"] = topic.get("uid")
                st.toast(tr("Cockpit Topic Loaded"))
                st.rerun()


def _scan_disk_tasks(tasks_root: str, limit: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not os.path.isdir(tasks_root):
        return rows

    entries = []
    for name in os.listdir(tasks_root):
        path = os.path.join(tasks_root, name)
        if os.path.isdir(path):
            try:
                mtime = os.path.getmtime(path)
                UUID(name)
                entries.append((mtime, name, path))
            except (ValueError, TypeError):
                continue

    entries.sort(reverse=True)
    for mtime, task_id, path in entries[:limit]:
        final_video = os.path.join(path, "final-1.mp4")
        rows.append(
            {
                "task_id": task_id,
                "path": path,
                "has_video": os.path.isfile(final_video),
                "video_path": final_video if os.path.isfile(final_video) else "",
                "updated": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
            }
        )
    return rows


def render_tasks_tab(
    tasks_root: str,
    tr: Callable[[str], str],
    open_folder_cb: Callable[[str], None],
) -> None:
    from app.services import state as sm

    st.subheader(tr("Cockpit Tab Tasks"))

    memory_tasks, total = sm.state.get_all_tasks(page=1, page_size=50)
    disk_tasks = _scan_disk_tasks(tasks_root)

    if memory_tasks:
        st.write(f"**{tr('Cockpit Memory Tasks')}** ({total})")
        for task in memory_tasks:
            task_id = task.get("task_id", "")
            state = task.get("state")
            progress = task.get("progress", 0)
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.write(f"`{task_id}` · {progress}%")
            with cols[1]:
                if st.button(tr("Open Task Folder"), key=f"open_mem_{task_id}"):
                    open_folder_cb(task_id)
            with cols[2]:
                video = task.get("videos", [None])[0] if task.get("videos") else None
                if video and os.path.isfile(str(video)):
                    st.download_button(
                        tr("Download Video"),
                        data=open(video, "rb").read(),
                        file_name=os.path.basename(str(video)),
                        key=f"dl_mem_{task_id}",
                    )

    st.divider()
    st.write(f"**{tr('Cockpit Disk Tasks')}**")
    if not disk_tasks:
        st.info(tr("Cockpit No Tasks"))
        return

    for row in disk_tasks:
        cols = st.columns([3, 1, 1])
        with cols[0]:
            label = row["task_id"]
            if row["has_video"]:
                label += " · ✓"
            st.write(f"`{label}` · {row['updated']}")
        with cols[1]:
            if st.button(tr("Open Task Folder"), key=f"open_disk_{row['task_id']}"):
                open_folder_cb(row["task_id"])
        with cols[2]:
            if row["has_video"]:
                st.download_button(
                    tr("Download Video"),
                    data=open(row["video_path"], "rb").read(),
                    file_name="final-1.mp4",
                    key=f"dl_disk_{row['task_id']}",
                )


def run_preview(
    params: Any,
    include_audio: bool,
    tr: Callable[[str], str],
    root_dir: str,
) -> bool:
    from uuid import uuid4

    from app.services import llm, voice
    from app.utils import utils

    if not params.video_subject and not params.video_script:
        st.error(tr("Video Script and Subject Cannot Both Be Empty"))
        return False

    with st.status(tr("Cockpit Preview Running"), expanded=True) as status:
        status.write(tr("Cockpit Step Script"))
        script = params.video_script.strip()
        if not script:
            script = llm.generate_script(
                video_subject=params.video_subject,
                language=params.video_language,
                paragraph_number=params.paragraph_number,
                video_script_prompt=params.video_script_prompt,
                custom_system_prompt=params.custom_system_prompt,
            )
        if not script or script.startswith("Error:"):
            st.error(script or tr("Video Generation Failed"))
            status.update(state="error")
            return False

        status.write(tr("Cockpit Step Terms"))
        amount = 8 if params.match_materials_to_script else 5
        terms = llm.generate_terms(
            video_subject=params.video_subject,
            video_script=script,
            amount=amount,
            match_script_order=params.match_materials_to_script,
        )
        if isinstance(terms, str):
            terms_text = terms
        else:
            terms_text = ", ".join(terms)

        st.session_state["video_script"] = script
        st.session_state["video_terms"] = terms_text
        params.video_script = script
        params.video_terms = terms_text

        if include_audio and not params.custom_audio_file:
            status.write(tr("Cockpit Step TTS"))
            temp_dir = utils.storage_dir("temp", create=True)
            audio_file = os.path.join(temp_dir, f"preview-{uuid4()}.mp3")
            sub_maker = voice.tts(
                text=script,
                voice_name=params.voice_name,
                voice_rate=params.voice_rate,
                voice_file=audio_file,
                voice_volume=params.voice_volume,
            )
            if sub_maker and os.path.isfile(audio_file):
                with open(audio_file, "rb") as audio_fp:
                    st.audio(audio_fp.read(), format="audio/mp3")
            else:
                st.warning(tr("Cockpit Preview Audio Failed"))

        status.update(label=tr("Cockpit Preview Done"), state="complete")

    st.session_state["preview_ready"] = True
    st.success(tr("Cockpit Preview Ready"))
    return True


COCKPIT_CSS = """
<style>
.cockpit-stepper {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin: 0.5rem 0 1rem 0;
}
.cockpit-step {
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    border: 1px solid #334155;
    color: #94a3b8;
    font-size: 0.85rem;
}
.cockpit-step.active {
    border-color: #3b82f6;
    color: #fff;
    background: rgba(59, 130, 246, 0.15);
}
</style>
"""


def render_stepper(tr: Callable[[str], str], active_index: int = 0) -> None:
    steps = [
        tr("Cockpit Step Idea"),
        tr("Cockpit Step Script"),
        tr("Cockpit Step Media"),
        tr("Cockpit Step Voice"),
        tr("Cockpit Step Subtitles"),
        tr("Cockpit Step Assembly"),
        tr("Cockpit Step Export"),
    ]
    html = '<div class="cockpit-stepper">'
    for index, step in enumerate(steps):
        css_class = "cockpit-step active" if index <= active_index else "cockpit-step"
        html += f'<div class="{css_class}">{step}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
