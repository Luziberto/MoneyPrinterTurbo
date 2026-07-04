"""Operator cockpit helpers for the Streamlit WebUI."""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import streamlit as st


def _material_source_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(
            item.get("path")
            or item.get("source_file_path")
            or item.get("url")
            or ""
        ).strip()
    if isinstance(item, str):
        return item.strip()
    return str(item or "").strip()


def analyze_clip_materials(materials: list[Any] | None) -> dict[str, Any]:
    """Summarize clip diversity and repetition from task materials."""
    sources = [_material_source_key(item) for item in (materials or [])]
    sources = [source for source in sources if source]
    counter = Counter(sources)
    total = len(sources)
    unique = len(counter)
    repeated = {path: count for path, count in counter.items() if count > 1}

    warnings: list[str] = []
    if total == 0:
        warnings.append("no_materials")
    if repeated:
        warnings.append("repeated_sources")
    if total >= 3 and unique / total < 0.6:
        warnings.append("low_diversity")

    collector_items = [item for item in (materials or []) if isinstance(item, dict)]
    if collector_items:
        target = max(
            (
                int(item.get("target_clips") or 0)
                for item in collector_items
                if item.get("target_clips")
            ),
            default=0,
        )
        if target and total < target:
            warnings.append("partial_collector_job")

    return {
        "total_segments": total,
        "unique_sources": unique,
        "repeated_sources": repeated,
        "warnings": warnings,
        "sources": sources,
    }

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
                    f"{channel.get('mode', 'faceless')} · "
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


def list_render_blockers(
    video_source: str,
    voice_name: str,
    tr: Callable[[str], str],
) -> list[str]:
    """Return actionable blocker messages for preview/render."""
    blockers: list[str] = []

    llm_status, llm_detail = _llm_readiness(tr)
    if llm_status == tr("Cockpit Status Blocked"):
        blockers.append(f"LLM — {llm_detail}")

    collector_status, collector_detail = _collector_readiness(video_source, tr)
    if collector_status == tr("Cockpit Status Blocked"):
        blockers.append(f"Collector — {collector_detail}")

    tts_status, tts_detail = _tts_readiness(voice_name, tr)
    if tts_status == tr("Cockpit Status Blocked"):
        blockers.append(f"TTS — {tts_detail}")

    ffmpeg_status, ffmpeg_detail = _ffmpeg_readiness(tr)
    if ffmpeg_status == tr("Cockpit Status Blocked"):
        blockers.append(f"FFmpeg — {ffmpeg_detail}")

    return blockers


def render_provider_center(
    video_source: str,
    voice_name: str,
    tr: Callable[[str], str],
    *,
    expanded: bool | None = None,
) -> None:
    """Readiness grid inspired by Cenara provider center."""
    checks = [
        (tr("Cockpit Provider LLM"), *_llm_readiness(tr)),
        (tr("Cockpit Provider Collector"), *_collector_readiness(video_source, tr)),
        (tr("Cockpit Provider TTS"), *_tts_readiness(voice_name, tr)),
        (tr("Cockpit Provider FFmpeg"), *_ffmpeg_readiness(tr)),
        (tr("Cockpit Provider BGM"), *_bgm_readiness(tr)),
    ]
    if expanded is None:
        blocked_status = tr("Cockpit Status Blocked")
        expanded = any(status == blocked_status for _, status, _ in checks)
    with st.expander(tr("Cockpit Provider Center"), expanded=expanded):
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
    used_statuses = {"generated", "approved", "published"}
    used = [topic for topic in topics if topic.get("status") in used_statuses]

    filter_options = [
        (tr("Cockpit Topics Pending"), "pending"),
        (tr("Cockpit Topics Used"), "used"),
        (tr("Cockpit Topics All"), "all"),
    ]
    filter_labels = [label for label, _ in filter_options]
    filter_values = [value for _, value in filter_options]
    selected_filter = st.radio(
        tr("Cockpit Topics Filter"),
        options=filter_values,
        format_func=lambda value: filter_labels[filter_values.index(value)],
        horizontal=True,
        key=f"cockpit_topic_filter_{active}",
    )

    if selected_filter == "pending":
        visible = pending
        section_title = tr("Cockpit Pending Topics")
    elif selected_filter == "used":
        visible = used
        section_title = tr("Cockpit Used Topics")
    else:
        visible = topics
        section_title = tr("Cockpit All Topics")

    st.write(f"**{section_title}** ({len(visible)})")

    if not visible:
        st.info(tr("Cockpit No Topics"))
        return

    for topic in visible[:40]:
        topic_id = topic.get("id")
        uid = topic.get("uid", "—")
        category = topic.get("category", "—")
        status = topic.get("status", "—")
        profiles = topic.get("music_profiles") or []
        profile_label = ", ".join(profiles) if profiles else "—"

        cols = st.columns([1, 4, 1])
        with cols[0]:
            st.write(f"#{topic_id}")
            st.caption(uid[:8] if isinstance(uid, str) else uid)
        with cols[1]:
            st.write(topic.get("topic", ""))
            st.caption(
                f"{tr('Cockpit Topic Category')}: {category} · "
                f"{tr('Cockpit Topic Status')}: {status} · "
                f"{tr('Cockpit Topic Music')}: {profile_label}"
            )
        with cols[2]:
            if st.button(
                tr("Cockpit Load Topic"),
                key=f"load_topic_{topic.get('uid', topic_id)}",
            ):
                st.session_state["video_subject"] = topic.get("topic", "")
                st.session_state["preview_ready"] = False
                st.session_state["loaded_topic_uid"] = topic.get("uid")
                st.session_state["loaded_topic_id"] = topic_id
                if profiles:
                    from app.config import config

                    config.ui["bgm_type"] = "profile_random"
                    config.ui["bgm_profile"] = profiles[0]
                st.toast(tr("Cockpit Topic Loaded"))
                st.rerun()


def render_option_cards(
    label: str,
    options: list[tuple[str, str]],
    selected: str,
    state_key: str,
) -> str:
    """Clickable option cards (VisualAI-style) backed by session state."""
    option_values = [value for _, value in options]
    if state_key not in st.session_state or st.session_state[state_key] not in option_values:
        st.session_state[state_key] = selected if selected in option_values else option_values[0]

    st.markdown(f'<p class="cockpit-card-group-label">{label}</p>', unsafe_allow_html=True)
    cols = st.columns(len(options))
    for index, (option_label, option_value) in enumerate(options):
        with cols[index]:
            active = st.session_state[state_key] == option_value
            if st.button(
                option_label,
                key=f"{state_key}_{option_value}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state[state_key] = option_value

    return str(st.session_state[state_key])


def render_clip_diagnosis(
    result: dict[str, Any],
    tr: Callable[[str], str],
) -> None:
    """Post-render card with clip source diversity and repetition warnings."""
    diagnosis = analyze_clip_materials(result.get("materials"))
    if diagnosis["total_segments"] == 0:
        return

    with st.expander(tr("Cockpit Clip Diagnosis"), expanded=True):
        metric_cols = st.columns(3)
        with metric_cols[0]:
            st.metric(tr("Cockpit Clip Total"), diagnosis["total_segments"])
        with metric_cols[1]:
            st.metric(tr("Cockpit Clip Unique"), diagnosis["unique_sources"])
        with metric_cols[2]:
            repeated_count = len(diagnosis["repeated_sources"])
            st.metric(tr("Cockpit Clip Repeated"), repeated_count)

        warning_labels = {
            "no_materials": tr("Cockpit Warn No Materials"),
            "repeated_sources": tr("Cockpit Warn Repeated Sources"),
            "low_diversity": tr("Cockpit Warn Low Diversity"),
            "partial_collector_job": tr("Cockpit Warn Partial Collector"),
        }
        for warning in diagnosis["warnings"]:
            st.warning(warning_labels.get(warning, warning))

        if diagnosis["repeated_sources"]:
            st.caption(tr("Cockpit Repeated Detail"))
            for path, count in sorted(
                diagnosis["repeated_sources"].items(),
                key=lambda item: item[1],
                reverse=True,
            )[:8]:
                st.text(f"×{count}  {os.path.basename(path) or path}")


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


def _task_state_label(state: Any, tr: Callable[[str], str]) -> str:
    from app.models import const

    mapping = {
        const.TASK_STATE_PROCESSING: tr("Cockpit Task Running"),
        const.TASK_STATE_COMPLETE: tr("Cockpit Task Complete"),
        const.TASK_STATE_FAILED: tr("Cockpit Task Failed"),
    }
    return mapping.get(state, tr("Cockpit Task Unknown"))


def _summarize_task_states(tasks: list[dict[str, Any]], tr: Callable[[str], str]) -> dict[str, int]:
    from app.models import const

    summary = {
        tr("Cockpit Task Running"): 0,
        tr("Cockpit Task Complete"): 0,
        tr("Cockpit Task Failed"): 0,
        tr("Cockpit Task Unknown"): 0,
    }
    for task in tasks:
        label = _task_state_label(task.get("state"), tr)
        summary[label] = summary.get(label, 0) + 1
    return {label: count for label, count in summary.items() if count > 0}


def render_runtime_panel(tr: Callable[[str], str]) -> None:
    from app.services.runtime_limits import (
        clear_stale_generation_lock,
        generation_lock_status,
        get_runtime_limits,
    )

    limits = get_runtime_limits()
    lock = generation_lock_status()
    cols = st.columns(4)
    with cols[0]:
        st.metric(tr("Cockpit Runtime Threads"), limits.max_threads)
    with cols[1]:
        st.metric(tr("Cockpit Runtime Remote MB"), limits.max_remote_video_mb)
    with cols[2]:
        st.metric(tr("Cockpit Runtime Downloads"), limits.max_downloads_per_task)
    with cols[3]:
        lock_label = tr("Cockpit Runtime Lock Free")
        if lock:
            lock_label = tr("Cockpit Runtime Lock Busy")
        st.metric(tr("Cockpit Runtime Lock"), lock_label)

    if lock:
        st.warning(
            f"{tr('Cockpit Runtime Lock Active')}: `{lock.get('task_id', 'unknown')}`"
        )
    action_cols = st.columns([1, 1, 2])
    with action_cols[0]:
        if st.button(tr("Cockpit Clear Stale Lock"), key="cockpit_clear_stale_lock"):
            if clear_stale_generation_lock():
                st.toast(tr("Cockpit Stale Lock Cleared"))
            else:
                st.toast(tr("Cockpit No Stale Lock"))
            st.rerun()
    with action_cols[1]:
        if st.button(tr("Cockpit Force Clear Lock"), key="cockpit_force_clear_lock"):
            if clear_stale_generation_lock(force=True):
                st.toast(tr("Cockpit Lock Force Cleared"))
            else:
                st.toast(tr("Cockpit No Lock To Clear"))
            st.rerun()


def render_tasks_tab(
    tasks_root: str,
    tr: Callable[[str], str],
    open_folder_cb: Callable[[str], None],
) -> None:
    from app.models import const
    from app.services import state as sm

    st.subheader(tr("Cockpit Tab Tasks"))
    render_runtime_panel(tr)

    memory_tasks, total = sm.state.get_all_tasks(page=1, page_size=100)
    disk_tasks = _scan_disk_tasks(tasks_root, limit=100)
    disk_by_id = {row["task_id"]: row for row in disk_tasks}

    if memory_tasks:
        summary = _summarize_task_states(memory_tasks, tr)
        if summary:
            metric_cols = st.columns(len(summary))
            for index, (label, count) in enumerate(summary.items()):
                with metric_cols[index % len(metric_cols)]:
                    st.metric(label, count)

        table_rows = []
        for task in memory_tasks:
            task_id = str(task.get("task_id", ""))
            disk = disk_by_id.get(task_id, {})
            table_rows.append(
                {
                    tr("Cockpit Task Id"): task_id[:8] + "…",
                    tr("Cockpit Task State"): _task_state_label(task.get("state"), tr),
                    tr("Cockpit Task Progress"): f"{task.get('progress', 0)}%",
                    tr("Cockpit Task Updated"): disk.get("updated", "—"),
                    tr("Cockpit Task Video"): "✓" if disk.get("has_video") else "—",
                }
            )
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        st.write(f"**{tr('Cockpit Memory Tasks')}** ({total})")
        for task in memory_tasks[:30]:
            task_id = str(task.get("task_id", ""))
            disk = disk_by_id.get(task_id, {})
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.write(
                    f"`{task_id}` · {_task_state_label(task.get('state'), tr)} · "
                    f"{task.get('progress', 0)}%"
                )
            with cols[1]:
                if st.button(tr("Open Task Folder"), key=f"open_mem_{task_id}"):
                    open_folder_cb(task_id)
            with cols[2]:
                video_path = disk.get("video_path") or (
                    task.get("videos", [None])[0] if task.get("videos") else None
                )
                if video_path and os.path.isfile(str(video_path)):
                    st.download_button(
                        tr("Download Video"),
                        data=open(video_path, "rb").read(),
                        file_name=os.path.basename(str(video_path)),
                        key=f"dl_mem_{task_id}",
                    )
            with cols[3]:
                if task.get("state") != const.TASK_STATE_PROCESSING:
                    if st.button(tr("Cockpit Remove Task"), key=f"rm_mem_{task_id}"):
                        sm.state.delete_task(task_id)
                        st.toast(tr("Cockpit Task Removed"))
                        st.rerun()
    else:
        st.info(tr("Cockpit No Memory Tasks"))

    st.divider()
    st.write(f"**{tr('Cockpit Disk Tasks')}** ({len(disk_tasks)})")
    if not disk_tasks:
        st.info(tr("Cockpit No Tasks"))
        return

    for row in disk_tasks[:30]:
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
.cockpit-card-group-label {
    font-size: 0.9rem;
    font-weight: 600;
    margin: 0.25rem 0 0.5rem 0;
}
.cockpit-card-group-label + div[data-testid="stHorizontalBlock"] button {
    min-height: 2.75rem;
    border-radius: 0.75rem;
    font-weight: 600;
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
