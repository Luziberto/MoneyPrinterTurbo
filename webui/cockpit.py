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

def assign_model_fields(model: Any, **values: Any) -> None:
    """Set Pydantic fields when supported by the installed model version."""
    fields = getattr(model.__class__, "model_fields", {})
    for key, value in values.items():
        if key in fields:
            setattr(model, key, value)


def model_supports_field(model: Any, field_name: str) -> bool:
    fields = getattr(model.__class__, "model_fields", {})
    return field_name in fields


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


RUNTIME_SESSION_KEYS = (
    "video_subject",
    "paragraph_number_input",
    "match_materials_to_script",
    "video_script_prompt",
    "title_enabled",
    "title_text",
    "title_duration",
    "script_mode",
)

RUNTIME_UI_KEYS = (
    "video_source",
    "bgm_type",
    "bgm_profile",
    "bgm_file",
    "bgm_volume",
    "font_name",
    "font_size",
    "subtitle_position",
    "text_fore_color",
    "voice_name",
    "voice_volume",
    "voice_rate",
    "tts_server",
    "video_aspect",
    "video_language",
    "subtitle_enabled",
    "stroke_color",
    "stroke_width",
    "subtitle_background_enabled",
    "subtitle_background_color",
    "rounded_subtitle_background",
    "custom_position",
    "video_concat_mode",
    "video_transition_mode",
    "video_clip_duration",
    "video_count",
)

RUNTIME_TRACKED_KEYS = RUNTIME_SESSION_KEYS + RUNTIME_UI_KEYS

STEP_IDS = (
    "idea",
    "script",
    "collector",
    "preview",
    "render",
    "result",
)

PIPELINE_STEP_COUNT = len(STEP_IDS)


def pipeline_step_labels(tr: Callable[[str], str]) -> list[str]:
    return [
        tr("Cockpit Step Idea"),
        tr("Cockpit Step Script"),
        tr("Cockpit Step Collector"),
        tr("Cockpit Step Preview"),
        tr("Cockpit Step Render"),
        tr("Cockpit Step Result"),
    ]


def _effective_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    """Merge channel runtime with current form overrides for display."""
    from app.config import config

    effective = dict(runtime or {})
    form = collect_form_state()
    for key, value in form.items():
        if value is not None and value != "":
            effective[key] = value
    for key in RUNTIME_UI_KEYS:
        if key in config.ui:
            effective[key] = config.ui[key]
    if "cockpit_video_source" in st.session_state:
        effective["video_source"] = st.session_state["cockpit_video_source"]
    return effective


def _collector_limits_from_runtime(runtime: dict[str, Any] | None = None) -> tuple[int, int]:
    runtime = runtime or st.session_state.get("channel_runtime") or {}
    collector = runtime.get("collector") or {}
    target = int(collector.get("target_clips", 25) or 25)
    minimum = int(collector.get("min_acceptable_clips", 20) or 20)
    return target, minimum


def _count_keywords(terms_text: str) -> int:
    if not terms_text or not str(terms_text).strip():
        return 0
    return len([part for part in str(terms_text).split(",") if part.strip()])


def _collector_job_snapshot() -> dict[str, Any]:
    return dict(st.session_state.get("last_collector_job") or {})


def save_collector_job_snapshot(job: Any) -> None:
    """Persist collector job metrics for cockpit UI."""
    if job is None:
        return
    if hasattr(job, "model_dump"):
        payload = job.model_dump()
    elif isinstance(job, dict):
        payload = dict(job)
    else:
        return
    reused = int(payload.get("local_reused") or 0)
    downloads = int(payload.get("new_downloads") or 0)
    total = reused + downloads
    payload["cache_hit_pct"] = round((reused / total) * 100) if total else None
    st.session_state["last_collector_job"] = payload


def compute_pipeline_step_states(
    *,
    video_source: str = "collector",
) -> list[str]:
    """Return per-step status: done, active, pending."""
    active = int(st.session_state.get("cockpit_active_step", 0) or 0)
    active = max(0, min(active, PIPELINE_STEP_COUNT - 1))

    done = [False] * PIPELINE_STEP_COUNT
    done[0] = bool(str(st.session_state.get("video_subject", "") or "").strip())
    done[1] = bool(str(st.session_state.get("video_script", "") or "").strip())

    if video_source == "collector":
        job = _collector_job_snapshot()
        done[2] = (
            job.get("status") == "ready"
            or int(job.get("selected_clips_count") or 0) > 0
        )
    else:
        done[2] = done[1]

    done[3] = bool(st.session_state.get("preview_ready"))

    last_task = st.session_state.get("last_render_task_id")
    if last_task:
        tasks_root = ROOT_DIR / "storage" / "tasks" / str(last_task)
        if (tasks_root / "final-1.mp4").is_file():
            done[4] = True
            done[5] = True

    states: list[str] = []
    for index in range(PIPELINE_STEP_COUNT):
        if index == active:
            states.append("active")
        elif done[index]:
            states.append("done")
        else:
            states.append("pending")
    return states


def _pipeline_dot_emoji(status: str) -> str:
    return {
        "done": "🟢",
        "active": "🟠",
        "pending": "⚪",
        "blocked": "🔴",
    }.get(status, "⚪")


def render_pipeline_nav(tr: Callable[[str], str]) -> None:
    """Clickable horizontal pipeline (visual track, not navbar)."""
    _init_cockpit_session_state()
    from app.config import config

    active_index = int(st.session_state.get("cockpit_active_step", _default_active_step()) or 0)
    active_index = max(0, min(active_index, PIPELINE_STEP_COUNT - 1))
    st.session_state["cockpit_active_step"] = active_index

    video_source = str(
        st.session_state.get(
            "cockpit_video_source",
            config.ui.get("video_source", "collector"),
        )
        or "collector"
    )
    labels = pipeline_step_labels(tr)
    states = compute_pipeline_step_states(video_source=video_source)

    st.markdown('<div class="cockpit-pipeline-track">', unsafe_allow_html=True)
    nav_cols = st.columns(PIPELINE_STEP_COUNT)
    for step_index, label in enumerate(labels):
        state = states[step_index]
        dot = _pipeline_dot_emoji(state)
        suffix = " ✔" if state == "done" else ""
        is_active = step_index == active_index
        with nav_cols[step_index]:
            if st.button(
                f"{dot} {label}{suffix}",
                key=f"pipeline_nav_{step_index}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["cockpit_active_step"] = step_index
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _channel_header_meta_line(channel: dict[str, Any], runtime: dict[str, Any], tr: Callable[[str], str]) -> str:
    effective = _effective_runtime(runtime)
    mode = str(effective.get("mode") or channel.get("mode") or "faceless")
    duration = str(effective.get("target_duration") or channel.get("target_duration") or "—")
    source = _format_summary_value("video_source", effective, tr)
    voice = _format_summary_value("voice_name", effective, tr)
    bgm = _format_summary_value("bgm_type", effective, tr)
    if effective.get("bgm_profile"):
        bgm = str(effective.get("bgm_profile"))
    return f"{mode} • {duration}s • {source} • {voice} • {bgm}"


def render_channel_header(
    channels: list[str],
    tr: Callable[[str], str],
) -> str | None:
    """Compact sticky channel header with dropdown."""
    from app.config import config

    _init_cockpit_session_state()

    if "active_channel" not in st.session_state:
        saved = config.ui.get("active_channel", "")
        st.session_state["active_channel"] = (
            saved if saved in channels else (channels[0] if channels else "")
        )

    if not channels:
        st.caption(tr("Cockpit No Channels"))
        return None

    previous = st.session_state.get("active_channel", "")
    selected = previous
    if previous in channels:
        index = channels.index(previous)
    else:
        index = 0
        selected = channels[0]

    channel_config: dict[str, Any] = {}
    runtime = st.session_state.get("channel_runtime") or {}
    if selected:
        try:
            channel_config = load_channel_config(selected)
            if not runtime:
                runtime = build_runtime_config(selected)
        except FileNotFoundError:
            channel_config = {"name": selected, "slug": selected}

    display_name = str(channel_config.get("name") or selected or "—")

    ch_label, ch_select = st.columns([1.2, 3])
    with ch_label:
        st.markdown(
            f'<div class="cockpit-channel-inline">🟢 {tr("Cockpit Channel Live")}: '
            f'<strong>{display_name}</strong></div>',
            unsafe_allow_html=True,
        )
    with ch_select:
        selected = st.selectbox(
            tr("Cockpit Active Channel"),
            options=channels,
            index=index,
            key="cockpit_channel_select",
            label_visibility="collapsed",
        )

    if selected != previous:
        selected = handle_channel_selection(selected, previous, tr)

    if st.session_state.get("pending_channel_switch"):
        render_channel_switch_dialog(tr)

    if selected and not st.session_state.get("channel_runtime"):
        apply_runtime_config(build_runtime_config(selected), selected)

    st.session_state["active_channel"] = selected
    config.ui["active_channel"] = selected
    return selected


def render_channel_toolbar(
    channels: list[str],
    tr: Callable[[str], str],
) -> str | None:
    """Backward-compatible alias for channel header."""
    return render_channel_header(channels, tr)


def _prod_badge(text: str, *, tone: str = "default") -> str:
    return f'<span class="cockpit-badge cockpit-badge-{tone}">{text}</span>'


def _render_production_badges(
    *,
    video_badges: list[str],
    audio_badges: list[str],
    prod_badges: list[str],
    compact: bool = False,
) -> str:
    groups: list[tuple[str, list[str]]] = [("VÍDEO", video_badges)]
    if not compact:
        groups.extend([("ÁUDIO", audio_badges), ("PRODUÇÃO", prod_badges)])
    parts = ['<div class="cockpit-prod-header">']
    for label, badges in groups:
        parts.append('<div class="cockpit-prod-group">')
        parts.append(f'<div class="cockpit-prod-group-label">{label}</div>')
        parts.append(f'<div class="cockpit-prod-badges">{"".join(badges)}</div>')
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


def render_production_summary(
    runtime: dict[str, Any],
    tr: Callable[[str], str],
) -> None:
    """Production header with grouped badges."""
    from app.config import config

    effective = _effective_runtime(runtime)
    overrides = refresh_channel_overrides()
    collapsed = bool(st.session_state.get("production_summary_collapsed", False))

    target_clips, _ = _collector_limits_from_runtime(runtime)
    video_source = _format_summary_value("video_source", effective, tr)
    aspect = str(effective.get("video_aspect") or "—")
    tts = str(config.ui.get("tts_server", "azure-tts-v1") or "azure")
    if tts.startswith("azure"):
        tts_label = "Azure"
    else:
        tts_label = tts.replace("-tts", "").title()
    voice = _format_summary_value("voice_name", effective, tr)
    bgm = _format_summary_value("bgm_type", effective, tr)
    if effective.get("bgm_profile"):
        bgm = str(effective.get("bgm_profile"))
    duration = str(effective.get("target_duration") or "—")
    mode = str(effective.get("mode") or "faceless")

    video_ov = bool(overrides & {"video_source", "video_aspect", "video_clip_duration"})
    audio_ov = bool(overrides & {"voice_name", "bgm_type", "bgm_profile"})

    video_badges = [
        _prod_badge(video_source, tone="accent" if video_ov else "default"),
        _prod_badge(aspect),
        _prod_badge(f"{target_clips} clips", tone="metric"),
    ]
    audio_badges = [
        _prod_badge(voice, tone="accent" if audio_ov else "default"),
        _prod_badge(tts_label),
        _prod_badge(bgm),
    ]
    prod_badges = [
        _prod_badge(f"{duration}s", tone="metric"),
        _prod_badge(mode.title()),
    ]

    st.markdown(
        _render_production_badges(
            video_badges=video_badges,
            audio_badges=audio_badges,
            prod_badges=prod_badges,
            compact=collapsed,
        ),
        unsafe_allow_html=True,
    )

    collapsed_toggle = st.checkbox(
        tr("Cockpit Collapse Production Summary"),
        value=collapsed,
        key="production_summary_collapsed_cb",
    )
    st.session_state["production_summary_collapsed"] = collapsed_toggle


def render_ops_bar(tr: Callable[[str], str], video_source: str) -> None:
    """Discrete one-line collector ops strip."""
    if video_source != "collector":
        return

    from app.config import config
    from app.services import collector_client

    status_label, _ = _collector_readiness(video_source, tr)
    ready = status_label == tr("Cockpit Status Ready")
    dot = "🟢" if ready else "🔴"

    dashboard: dict[str, Any] = {}
    try:
        dashboard = collector_client.fetch_collector_dashboard()
    except Exception:
        dashboard = {}

    library = dashboard.get("library_count")
    library_display = str(library) if library is not None else "—"
    quota = dashboard.get("quota_remaining")
    quota_display = str(quota) if quota is not None else "—"
    worker = dashboard.get("worker_status") or "—"

    st.markdown(
        f'<div class="cockpit-ops-bar">'
        f"<span>Collector {dot} {'Ready' if ready else 'Down'}</span>"
        f"<span>Library {library_display}</span>"
        f"<span>Quota {quota_display}</span>"
        f"<span>Worker {worker}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_context_row(label: str, value: str) -> None:
    st.markdown(
        f'<div class="cockpit-context-row">'
        f'<span class="cockpit-context-label">{label}</span>'
        f'<span class="cockpit-context-value">{value}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_context_badges(pairs: list[tuple[str, str]]) -> None:
    chips = []
    for label, value in pairs:
        chips.append(
            f'<div class="cockpit-ctx-chip">'
            f'<span class="cockpit-ctx-chip-label">{label}</span>'
            f'<span class="cockpit-ctx-chip-value">{value}</span>'
            f"</div>"
        )
    st.markdown(
        f'<div class="cockpit-context-badges">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


def render_document_stage(title: str) -> None:
    """Document-style stage header for the main editor column."""
    st.markdown(
        f'<div class="cockpit-doc-stage">'
        f'<div class="cockpit-doc-title">{title}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_document_divider() -> None:
    st.markdown('<div class="cockpit-doc-divider"></div>', unsafe_allow_html=True)


def render_document_section_label(label: str) -> None:
    st.markdown(f'<div class="cockpit-doc-section-label">{label}</div>', unsafe_allow_html=True)


def render_section_title(title: str, *, extra_class: str = "") -> None:
    css_class = "cockpit-section-title"
    if extra_class:
        css_class = f"{css_class} {extra_class}"
    st.markdown(f'<div class="{css_class}">{title}</div>', unsafe_allow_html=True)


def render_stage_context(
    step_id: str,
    runtime: dict[str, Any],
    params: Any,
    tr: Callable[[str], str],
) -> None:
    """Read-only stage context card (top of right panel)."""
    from app.config import config

    effective = _effective_runtime(runtime)
    channel_name = str(effective.get("name") or effective.get("slug") or "—")

    st.markdown(
        f'<div class="cockpit-context-panel">'
        f'<div class="cockpit-context-panel-title">{tr("Cockpit Stage Context")}</div>',
        unsafe_allow_html=True,
    )

    if step_id == "idea":
        provider = str(config.app.get("llm_provider") or "—")
        _render_context_badges([
            (tr("Cockpit Context Channel"), channel_name),
            (tr("Cockpit Context Niche"), str(effective.get("video_subject") or params.video_subject or "—")),
            (tr("Cockpit Context LLM"), provider),
        ])

    elif step_id == "script":
        script = str(st.session_state.get("video_script") or "")
        words = len(script.split()) if script else 0
        _render_context_badges([
            (tr("Cockpit Context Channel"), channel_name),
            (tr("Video Subject"), str(params.video_subject or "—")),
            (tr("Cockpit Context Words"), f"~{words}"),
        ])

    elif step_id == "collector":
        job = _collector_job_snapshot()
        terms = str(st.session_state.get("video_terms") or "")
        target, _ = _collector_limits_from_runtime(runtime)
        cache_local = job.get("local_reused", "—")
        _render_context_badges([
            (tr("Cockpit Context Channel"), channel_name),
            (tr("Cockpit Context Keywords"), str(_count_keywords(terms))),
            (tr("Cockpit Context Target Clips"), str(target)),
            (tr("Cockpit Context Cache"), f"{cache_local}"),
        ])

    elif step_id == "preview":
        lang = str(params.video_language or effective.get("video_language") or "—")
        _render_context_badges([
            (tr("Cockpit Context Channel"), channel_name),
            (tr("Cockpit Context Language"), lang or tr("Auto Detect")),
            (tr("Speech Synthesis"), _format_summary_value("voice_name", effective, tr)),
            (tr("Background Music"), _format_summary_value("bgm_type", effective, tr)),
        ])

    elif step_id == "render":
        task_id = st.session_state.get("last_render_task_id") or st.session_state.get(
            "last_preview_task_id", "—"
        )
        _render_context_badges([
            (tr("Cockpit Context Channel"), channel_name),
            (tr("Cockpit Task Id"), str(task_id)[:12]),
        ])

    elif step_id == "result":
        task_id = st.session_state.get("last_render_task_id", "—")
        _render_context_badges([
            (tr("Cockpit Context Channel"), channel_name),
            (tr("Cockpit Task Id"), str(task_id)[:12]),
            (tr("Cockpit Target Duration"), str(effective.get("target_duration") or "—")),
        ])

    st.markdown("</div>", unsafe_allow_html=True)


def render_stage_inspector(
    step_id: str,
    runtime: dict[str, Any],
    params: Any,
    tr: Callable[[str], str],
    *,
    inspector_callbacks: Any = None,
) -> tuple[list, Any]:
    """Route to step-specific configuration inspector."""
    from webui import cockpit_inspector

    return cockpit_inspector.render_stage_inspector(
        step_id,
        runtime,
        params,
        tr,
        callbacks=inspector_callbacks,
    )


def _preview_checklist_state(video_source: str, runtime: dict[str, Any], tr: Callable[[str], str]) -> list[tuple[str, bool]]:
    effective = _effective_runtime(runtime)
    has_script = bool(str(st.session_state.get("video_script", "") or "").strip())
    has_terms = bool(str(st.session_state.get("video_terms", "") or "").strip())
    job = _collector_job_snapshot()
    collector_ok = video_source != "collector" or job.get("status") == "ready" or int(
        job.get("selected_clips_count") or 0
    ) > 0
    voice_ok = bool(str(effective.get("voice_name") or "").strip())
    bgm_ok = bool(str(effective.get("bgm_type") or "").strip())
    return [
        (tr("Cockpit Step Script"), has_script),
        (tr("Video Keywords"), has_terms),
        (tr("Cockpit Step Collector"), collector_ok),
        (tr("Speech Synthesis"), voice_ok),
        (tr("Background Music"), bgm_ok),
    ]


def _preview_checklist_html(items: list[tuple[str, bool]]) -> str:
    rows = []
    for label, done in items:
        state_cls = "cockpit-check-done" if done else "cockpit-check-pending"
        icon = "✔" if done else "○"
        rows.append(
            f'<div class="cockpit-check-row {state_cls}">'
            f'<span class="cockpit-check-icon">{icon}</span>'
            f"<span>{label}</span>"
            f"</div>"
        )
    return (
        f'<div class="cockpit-approval-gate">'
        f'{"".join(rows)}'
        f'<div class="cockpit-approval-divider"></div>'
        f"</div>"
    )


def render_preview_editor(
    params: Any,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
    *,
    video_source: str,
) -> tuple[bool, bool, bool]:
    """Preview gate editor. Returns (preview_btn, include_audio, skip_preview)."""
    render_document_stage(tr("Cockpit Step Preview"))
    checklist = _preview_checklist_state(video_source, runtime, tr)
    st.markdown(_preview_checklist_html(checklist), unsafe_allow_html=True)

    include_audio = st.checkbox(
        tr("Cockpit Preview Include Audio"),
        value=False,
        key="cockpit_preview_audio",
    )
    skip_preview = st.checkbox(
        tr("Cockpit Skip Preview Gate"),
        value=st.session_state.get("cockpit_skip_preview", False),
        key="cockpit_skip_preview_cb",
    )
    st.session_state["cockpit_skip_preview"] = skip_preview

    st.markdown('<div class="cockpit-cta-bar">', unsafe_allow_html=True)
    preview_btn = st.button(
        tr("Cockpit Preview"),
        type="primary",
        use_container_width=True,
        key="cockpit_preview_gate_btn",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    render_document_divider()
    st.markdown(f"**{tr('Cockpit Last Preview')}**")
    last_at = st.session_state.get("last_preview_at")
    last_task = st.session_state.get("last_preview_task_id")
    if last_at:
        st.caption(str(last_at))
    else:
        st.caption("—")

    action_cols = st.columns(2)
    with action_cols[0]:
        if last_task and st.button(tr("Cockpit Open Preview"), key="cockpit_open_preview"):
            preview_dir = ROOT_DIR / "storage" / "tasks" / str(last_task)
            if preview_dir.is_dir():
                st.session_state["cockpit_open_folder"] = str(preview_dir)
    with action_cols[1]:
        regen = st.button(tr("Cockpit Regenerate Preview"), key="cockpit_regen_preview")
        if regen:
            preview_btn = True

    return preview_btn, include_audio, skip_preview


def render_render_editor(
    params: Any,
    tr: Callable[[str], str],
) -> bool:
    """Render step editor — returns whether render was requested."""
    render_document_stage(tr("Cockpit Step Render"))
    if st.session_state.get("preview_ready"):
        st.success(tr("Cockpit Preview Ready"))
    else:
        st.warning(tr("Cockpit Assembly Need Preview"))

    st.caption(tr("Cockpit Render Hint"))
    st.markdown('<div class="cockpit-cta-bar">', unsafe_allow_html=True)
    render_btn = st.button(
        tr("Cockpit Render Video"),
        type="primary",
        use_container_width=True,
        key="cockpit_render_gate_btn",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return render_btn


def _render_result_actions(
    tr: Callable[[str], str],
    *,
    path: str | None,
    task_id: str,
    open_folder_cb: Callable[[str], None] | None,
    key_prefix: str,
    copy_text: str | None = None,
) -> None:
    """Action row for result artifact cards."""
    cols = st.columns(3)
    with cols[0]:
        if path and st.button(tr("Cockpit Result Open"), key=f"{key_prefix}_open"):
            if open_folder_cb and task_id:
                open_folder_cb(task_id)
    with cols[1]:
        if copy_text and st.button(tr("Cockpit Result Copy"), key=f"{key_prefix}_copy"):
            st.session_state["cockpit_clipboard"] = copy_text
            st.toast(tr("Cockpit Result Copied"))
    with cols[2]:
        if task_id and open_folder_cb and st.button(
            tr("Cockpit Result Folder"), key=f"{key_prefix}_folder"
        ):
            open_folder_cb(task_id)


def render_result_editor(
    tr: Callable[[str], str],
    *,
    open_folder_cb: Callable[[str], None] | None = None,
) -> None:
    """Result step — artifact cards with actions."""
    task_id = str(st.session_state.get("last_render_task_id") or "")
    task_dir = ROOT_DIR / "storage" / "tasks" / task_id if task_id else None

    render_document_stage(tr("Cockpit Step Result"))

    st.markdown('<div class="cockpit-result-card">', unsafe_allow_html=True)
    st.markdown('<div class="cockpit-result-card-title">MP4</div>', unsafe_allow_html=True)
    video_path = task_dir / "final-1.mp4" if task_dir else None
    if video_path and video_path.is_file():
        st.video(str(video_path))
        st.download_button(
            tr("Download Video"),
            data=video_path.read_bytes(),
            file_name="final-1.mp4",
            key="cockpit_result_download",
        )
        _render_result_actions(
            tr,
            path=str(video_path),
            task_id=task_id,
            open_folder_cb=open_folder_cb,
            key_prefix="result_mp4",
            copy_text=str(video_path),
        )
    else:
        st.caption(tr("Cockpit Result No Artifact"))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="cockpit-result-card">', unsafe_allow_html=True)
    st.markdown('<div class="cockpit-result-card-title">Thumbnail</div>', unsafe_allow_html=True)
    thumb_candidates = ["thumbnail.jpg", "thumbnail.png", "thumb.jpg"]
    thumb_path = None
    if task_dir:
        for name in thumb_candidates:
            candidate = task_dir / name
            if candidate.is_file():
                thumb_path = candidate
                break
    if thumb_path:
        st.image(str(thumb_path))
        _render_result_actions(
            tr,
            path=str(thumb_path),
            task_id=task_id,
            open_folder_cb=open_folder_cb,
            key_prefix="result_thumb",
            copy_text=str(thumb_path),
        )
    else:
        st.caption(tr("Cockpit Result No Artifact"))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="cockpit-result-card">', unsafe_allow_html=True)
    st.markdown('<div class="cockpit-result-card-title">Metadata</div>', unsafe_allow_html=True)
    if task_dir and task_dir.is_dir():
        meta_files = ["script.json", "params.json", "subtitle.srt"]
        found = False
        for name in meta_files:
            path = task_dir / name
            if path.is_file():
                found = True
                st.caption(name)
                st.code(path.read_text(encoding="utf-8", errors="replace")[:2000])
                _render_result_actions(
                    tr,
                    path=str(path),
                    task_id=task_id,
                    open_folder_cb=open_folder_cb,
                    key_prefix=f"result_meta_{name}",
                    copy_text=str(path),
                )
        if not found:
            st.caption(tr("Cockpit Result No Artifact"))
    else:
        st.caption(tr("Cockpit Result No Artifact"))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="cockpit-result-card">', unsafe_allow_html=True)
    st.markdown('<div class="cockpit-result-card-title">Logs</div>', unsafe_allow_html=True)
    if task_dir:
        log_path = task_dir / "log.txt"
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            st.code("\n".join(lines[-40:]))
            _render_result_actions(
                tr,
                path=str(log_path),
                task_id=task_id,
                open_folder_cb=open_folder_cb,
                key_prefix="result_logs",
                copy_text=str(log_path),
            )
        else:
            st.caption(tr("Cockpit Result No Artifact"))
    else:
        st.caption(tr("Cockpit Result No Artifact"))
    st.markdown("</div>", unsafe_allow_html=True)


def render_collector_panel(
    params: Any,
    tr: Callable[[str], str],
) -> bool:
    """Collector stage editor. Returns True if fetch clips requested."""
    from app.config import config
    from app.services import collector_client

    render_document_stage(tr("Cockpit Step Collector"))

    dashboard: dict[str, Any] = {}
    try:
        dashboard = collector_client.fetch_collector_dashboard()
    except Exception:
        dashboard = {}

    lib_count = dashboard.get("library_count")
    lib_size = dashboard.get("library_size_tb")
    if lib_count is not None:
        lib_line = f"{lib_count:,} vídeos".replace(",", ".")
        if lib_size is not None:
            lib_line += f" · {lib_size} TB"
        lib_help = ""
    else:
        lib_line = tr("Cockpit Collector Library Empty")
        lib_help = tr("Cockpit Collector Library Hint")

    status_label, status_detail = _collector_readiness(
        str(params.video_source or "collector"),
        tr,
    )
    if status_label == tr("Cockpit Status Ready"):
        status_display = status_label
        status_help = status_detail[:60] if status_detail else ""
    else:
        status_display = status_label
        status_help = status_detail[:60] if status_detail else tr("Cockpit Collector Status Hint")

    job = _collector_job_snapshot()
    reused = int(job.get("local_reused") or 0)
    downloads = int(job.get("new_downloads") or 0)
    clips = int(job.get("selected_clips_count") or 0)
    hit = job.get("cache_hit_pct")
    if hit is not None:
        cache_display = f"{hit}%"
        cache_help = f"{reused} local · {downloads} new"
    elif job:
        cache_display = tr("Cockpit Collector Cache Pending")
        cache_help = tr("Cockpit Collector Cache Hint")
    else:
        cache_display = "—"
        cache_help = tr("Cockpit Collector Cache Hint")

    provider = job.get("provider") or job.get("last_provider")
    if provider:
        duration = job.get("duration_seconds") or job.get("elapsed_seconds")
        provider_display = str(provider)
        provider_help = f"{duration}s" if duration else ""
    else:
        provider_display = tr("Cockpit Collector No Job Yet")
        provider_help = tr("Cockpit Collector No Job Hint")

    cards = [
        (tr("Cockpit Collector Library"), lib_line, lib_help, "📚"),
        (tr("Cockpit Collector Status"), status_display, status_help, "📡"),
        (tr("Cockpit Cache Hit"), cache_display, cache_help, "⚡"),
        (tr("Cockpit Last Provider"), provider_display, provider_help, "🎬"),
    ]
    card_html = ['<div class="cockpit-collector-grid">']
    for title, value, hint, icon in cards:
        card_html.append(
            f'<div class="cockpit-collector-stat">'
            f'<div class="cockpit-collector-stat-icon">{icon}</div>'
            f'<div class="cockpit-collector-stat-label">{title}</div>'
            f'<div class="cockpit-collector-stat-value">{value}</div>'
            f'<div class="cockpit-collector-stat-hint">{hint}</div>'
            f"</div>"
        )
    card_html.append("</div>")
    st.markdown("".join(card_html), unsafe_allow_html=True)

    if job:
        st.caption(
            f"{tr('Cockpit Last Job')}: `{job.get('job_id', '—')}` · "
            f"{job.get('status', '—')} · "
            f"{reused} local / {downloads} new / {clips} clips"
        )

    st.markdown('<div class="cockpit-cta-bar">', unsafe_allow_html=True)
    fetch = st.button(
        tr("Cockpit Fetch Clips"),
        type="primary",
        use_container_width=True,
        key="cockpit_fetch_clips_btn",
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return fetch


def run_collector_fetch(params: Any, tr: Callable[[str], str]) -> bool:
    """Run collector job with current keywords (no full render)."""
    from uuid import uuid4

    from app.models.schema import CollectorJobRequest, normalize_collector_keywords
    from app.services import collector_client

    terms = str(st.session_state.get("video_terms") or params.video_terms or "")
    normalized = normalize_collector_keywords(terms)
    if not normalized.keywords:
        st.error(tr("Cockpit Collector Need Keywords"))
        return False

    target, minimum = _collector_limits_from_runtime()
    request = CollectorJobRequest(
        client_task_id=f"ui-{uuid4()}",
        keywords=normalized.keywords,
        target_clips=target,
        min_acceptable_clips=minimum,
    )

    with st.status(tr("Cockpit Collector Running"), expanded=True) as status:
        try:
            job = collector_client.create_stock_job(request)
            status.write(f"job_id={job.job_id}")
            final = collector_client.wait_for_stock_job(job.job_id)
            snapshot = final.model_dump()
            snapshot["provider"] = snapshot.get("provider") or "collector"
            save_collector_job_snapshot(snapshot)
            status.update(label=tr("Cockpit Collector Done"), state="complete")
            st.success(tr("Cockpit Collector Done"))
            return True
        except Exception as exc:
            status.update(state="error")
            st.error(str(exc))
            return False


def _normalize_runtime_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, bool):
        return bool(value)
    if value is None:
        return None
    if isinstance(value, (int, str)):
        return value
    return str(value)


def build_runtime_config(slug: str) -> dict[str, Any]:
    """Build a flat runtime snapshot from channel.json for form comparison."""
    channel = load_channel_config(slug)
    niche = str(channel.get("niche", "") or "").strip()
    voice_name = str(channel.get("voice_name", "") or "").strip()
    aspect = str(channel.get("video_aspect", "") or "").strip()
    transition = channel.get("video_transition_mode")
    if transition is not None and hasattr(transition, "value"):
        transition = transition.value

    runtime: dict[str, Any] = {
        "slug": slug,
        "name": str(channel.get("name", slug) or slug),
        "video_subject": niche,
        "paragraph_number_input": int(channel.get("paragraph_number", 1) or 1),
        "match_materials_to_script": bool(channel.get("match_materials_to_script", False)),
        "video_script_prompt": str(channel.get("video_script_prompt", "") or "").strip(),
        "title_enabled": bool(channel.get("title_enabled", False)),
        "title_text": str(
            channel.get("title_text", "") or channel.get("name", "") or ""
        ).strip(),
        "title_duration": float(channel.get("title_duration", 3.0) or 3.0),
        "video_source": str(channel.get("video_source", "collector") or "collector"),
        "bgm_type": str(channel.get("bgm_type", "random") or "random"),
        "bgm_profile": str(channel.get("bgm_profile", "") or ""),
        "bgm_file": "",
        "bgm_volume": float(channel.get("bgm_volume", 0.2) or 0.2),
        "font_name": str(channel.get("font_name", "Roboto-Bold.ttf") or "Roboto-Bold.ttf"),
        "font_size": int(channel.get("font_size", 55) or 55),
        "subtitle_position": str(channel.get("subtitle_position", "bottom") or "bottom"),
        "text_fore_color": str(channel.get("text_fore_color", "#FFFFFF") or "#FFFFFF"),
        "voice_name": voice_name,
        "voice_volume": float(channel.get("voice_volume", 1.0) or 1.0),
        "voice_rate": float(channel.get("voice_rate", 1.0) or 1.0),
        "tts_server": "azure-tts-v1",
        "video_aspect": aspect or "9:16",
        "video_language": str(channel.get("video_language", "") or ""),
        "subtitle_enabled": bool(channel.get("subtitle_enabled", True)),
        "stroke_color": str(channel.get("stroke_color", "#000000") or "#000000"),
        "stroke_width": float(channel.get("stroke_width", 2.5) or 2.5),
        "subtitle_background_enabled": bool(
            channel.get("subtitle_background_enabled", True)
        ),
        "subtitle_background_color": str(
            channel.get("subtitle_background_color", "#000000") or "#000000"
        ),
        "rounded_subtitle_background": bool(
            channel.get("rounded_subtitle_background", False)
        ),
        "custom_position": float(channel.get("custom_position", 70.0) or 70.0),
        "video_concat_mode": str(channel.get("video_concat_mode", "random") or "random"),
        "video_transition_mode": transition,
        "video_clip_duration": int(channel.get("video_clip_duration", 3) or 3),
        "video_count": int(channel.get("video_count", 1) or 1),
        "target_duration": str(channel.get("target_duration", "") or ""),
        "mode": str(channel.get("mode", "faceless") or "faceless"),
        "collector": dict(channel.get("collector") or {}),
    }
    return runtime


def collect_form_state() -> dict[str, Any]:
    """Read tracked form values from session_state and config.ui."""
    from app.config import config

    form: dict[str, Any] = {}
    for key in RUNTIME_SESSION_KEYS:
        if key in st.session_state:
            form[key] = st.session_state[key]
    for key in RUNTIME_UI_KEYS:
        if key in config.ui:
            form[key] = config.ui[key]
    if "cockpit_video_source" in st.session_state:
        form["video_source"] = st.session_state["cockpit_video_source"]
    elif "video_source" not in form:
        form["video_source"] = config.ui.get(
            "video_source", config.app.get("video_source", "pexels")
        )
    aspect_key = None
    source = form.get("video_source", "collector")
    card_key = f"cockpit_video_aspect_{source}"
    if card_key in st.session_state:
        form["video_aspect"] = st.session_state[card_key]
    return form


def detect_overrides(
    runtime: dict[str, Any],
    form: dict[str, Any],
) -> dict[str, tuple[Any, Any]]:
    """Return fields that differ from the channel runtime baseline."""
    overrides: dict[str, tuple[Any, Any]] = {}
    for key in RUNTIME_TRACKED_KEYS:
        if key not in runtime:
            continue
        runtime_val = _normalize_runtime_value(runtime.get(key))
        form_val = _normalize_runtime_value(form.get(key))
        if form_val is None and runtime_val in (None, "", 0, False):
            continue
        if form_val != runtime_val:
            overrides[key] = (runtime_val, form_val)
    return overrides


def apply_runtime_config(runtime: dict[str, Any], slug: str) -> None:
    """Apply channel runtime snapshot to session state and config.ui."""
    from app.config import config

    st.session_state["active_channel"] = slug
    st.session_state["channel_runtime"] = dict(runtime)
    st.session_state["channel_overrides"] = set()
    st.session_state["preview_ready"] = False

    niche = str(runtime.get("video_subject", "") or "").strip()
    if niche:
        st.session_state["video_subject"] = niche

    st.session_state["paragraph_number_input"] = int(
        runtime.get("paragraph_number_input", 1) or 1
    )
    st.session_state["match_materials_to_script"] = bool(
        runtime.get("match_materials_to_script", False)
    )
    st.session_state["video_script_prompt"] = str(
        runtime.get("video_script_prompt", "") or ""
    ).strip()
    st.session_state["title_enabled"] = bool(runtime.get("title_enabled", False))
    st.session_state["title_text"] = str(runtime.get("title_text", "") or "").strip()
    st.session_state["title_duration"] = float(runtime.get("title_duration", 3.0) or 3.0)

    for key in RUNTIME_UI_KEYS:
        value = runtime.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value == "" and key not in {
            "bgm_type",
            "bgm_profile",
            "video_language",
        }:
            continue
        config.ui[key] = value

    config.ui["active_channel"] = slug
    config.app["match_materials_to_script"] = bool(
        runtime.get("match_materials_to_script", False)
    )

    video_source = str(runtime.get("video_source", "collector") or "collector")
    st.session_state["cockpit_video_source"] = video_source
    aspect = str(runtime.get("video_aspect", "9:16") or "9:16")
    st.session_state[f"cockpit_video_aspect_{video_source}"] = aspect
    bgm_profile = str(runtime.get("bgm_profile", "") or "")
    if bgm_profile:
        st.session_state["cockpit_bgm_profile"] = bgm_profile


def apply_channel_defaults(slug: str) -> None:
    """Load channel.json defaults into Streamlit session state and config.ui."""
    apply_runtime_config(build_runtime_config(slug), slug)


def _init_cockpit_session_state() -> None:
    if "cockpit_active_step" not in st.session_state:
        st.session_state["cockpit_active_step"] = 0
    if "cockpit_collapsed_steps" not in st.session_state:
        st.session_state["cockpit_collapsed_steps"] = set()
    if "channel_overrides" not in st.session_state:
        st.session_state["channel_overrides"] = set()
    if "production_summary_collapsed" not in st.session_state:
        st.session_state["production_summary_collapsed"] = False
    if "last_collector_job" not in st.session_state:
        st.session_state["last_collector_job"] = {}


init_cockpit_session_state = _init_cockpit_session_state


def refresh_channel_overrides() -> set[str]:
    runtime = st.session_state.get("channel_runtime") or {}
    if not runtime:
        return set()
    overrides = set(detect_overrides(runtime, collect_form_state()).keys())
    st.session_state["channel_overrides"] = overrides
    return overrides


def restore_field_from_channel(field_key: str, tr: Callable[[str], str]) -> None:
    runtime = st.session_state.get("channel_runtime") or {}
    if field_key not in runtime:
        return
    value = runtime[field_key]
    if field_key in RUNTIME_SESSION_KEYS:
        st.session_state[field_key] = value
    else:
        from app.config import config

        config.ui[field_key] = value
        if field_key == "video_source":
            st.session_state["cockpit_video_source"] = value
        elif field_key == "video_aspect":
            source = runtime.get("video_source", "collector")
            st.session_state[f"cockpit_video_aspect_{source}"] = value
        elif field_key == "bgm_profile" and value:
            st.session_state["cockpit_bgm_profile"] = value
    st.session_state["preview_ready"] = False
    refresh_channel_overrides()
    st.toast(tr("Cockpit Restored From Channel"))


def sync_params_from_ui(params: Any) -> None:
    """Populate VideoParams from config.ui when controls are hidden (normal mode)."""
    from app.config import config

    from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode

    params.video_subject = str(st.session_state.get("video_subject", "") or "").strip()
    params.video_script = str(st.session_state.get("video_script", "") or "")
    params.video_terms = str(st.session_state.get("video_terms", "") or "")
    params.video_language = str(config.ui.get("video_language", "") or "")
    params.paragraph_number = int(st.session_state.get("paragraph_number_input", 1) or 1)
    params.video_script_prompt = str(st.session_state.get("video_script_prompt", "") or "")
    if st.session_state.get("use_custom_system_prompt"):
        params.custom_system_prompt = str(st.session_state.get("custom_system_prompt", "") or "")
    else:
        params.custom_system_prompt = ""
    params.match_materials_to_script = bool(
        st.session_state.get("match_materials_to_script", False)
    )

    source = str(
        st.session_state.get(
            "cockpit_video_source",
            config.ui.get("video_source", config.app.get("video_source", "pexels")),
        )
        or "pexels"
    )
    params.video_source = source

    aspect_val = config.ui.get("video_aspect", VideoAspect.portrait.value)
    if isinstance(aspect_val, VideoAspect):
        aspect_val = aspect_val.value
    card_key = f"cockpit_video_aspect_{source}"
    if card_key in st.session_state:
        aspect_val = st.session_state[card_key]
    params.video_aspect = VideoAspect(str(aspect_val))

    concat_val = config.ui.get("video_concat_mode", "random")
    params.video_concat_mode = VideoConcatMode(str(concat_val))

    transition_val = config.ui.get("video_transition_mode")
    if transition_val:
        params.video_transition_mode = VideoTransitionMode(str(transition_val))

    params.video_clip_duration = int(config.ui.get("video_clip_duration", 3) or 3)
    params.video_count = int(config.ui.get("video_count", 1) or 1)
    params.voice_name = str(config.ui.get("voice_name", "") or "")
    params.voice_volume = float(config.ui.get("voice_volume", 1.0) or 1.0)
    params.voice_rate = float(config.ui.get("voice_rate", 1.0) or 1.0)
    params.bgm_type = str(config.ui.get("bgm_type", "random") or "")
    params.bgm_profile = str(config.ui.get("bgm_profile", "") or "")
    params.bgm_file = str(config.ui.get("bgm_file", "") or "")
    params.bgm_volume = float(config.ui.get("bgm_volume", 0.2) or 0.2)

    params.subtitle_enabled = bool(config.ui.get("subtitle_enabled", True))
    params.font_name = str(config.ui.get("font_name", "Roboto-Bold.ttf") or "Roboto-Bold.ttf")
    params.font_size = int(config.ui.get("font_size", 55) or 55)
    params.subtitle_position = str(config.ui.get("subtitle_position", "bottom") or "bottom")
    params.text_fore_color = str(config.ui.get("text_fore_color", "#FFFFFF") or "#FFFFFF")
    params.stroke_color = str(config.ui.get("stroke_color", "#000000") or "#000000")
    params.stroke_width = float(config.ui.get("stroke_width", 2.5) or 2.5)
    params.custom_position = float(config.ui.get("custom_position", 70.0) or 70.0)
    params.rounded_subtitle_background = bool(
        config.ui.get("rounded_subtitle_background", False)
    )

    bg_enabled = bool(config.ui.get("subtitle_background_enabled", True))
    if bg_enabled:
        params.text_background_color = str(
            config.ui.get("subtitle_background_color", "#000000") or "#000000"
        )
    else:
        params.text_background_color = False

    params.title_enabled = bool(st.session_state.get("title_enabled", False))
    params.title_text = str(st.session_state.get("title_text", "") or "")
    params.title_duration = float(st.session_state.get("title_duration", 3.0) or 3.0)
    target, minimum = _collector_limits_from_runtime(
        st.session_state.get("channel_runtime") or {}
    )
    params.collector_target_clips = target
    params.collector_min_acceptable_clips = minimum
    assign_model_fields(params, script_mode=st.session_state.get("script_mode", "auto"))


def render_channel_switch_dialog(tr: Callable[[str], str]) -> None:
    """Show confirmation dialog when switching channels with unsaved overrides."""
    pending = st.session_state.get("pending_channel_switch")
    if not pending:
        return

    runtime = build_runtime_config(pending)
    target_name = str(runtime.get("name", pending))

    @st.dialog(tr("Cockpit Confirm Channel Switch"))
    def _dialog() -> None:
        st.warning(tr("Cockpit Unsaved Changes"))
        st.write(tr("Cockpit Switch Channel Message").format(channel=target_name))
        col_cancel, col_apply = st.columns(2)
        with col_cancel:
            if st.button(tr("Cockpit Cancel"), use_container_width=True):
                st.session_state.pop("pending_channel_switch", None)
                st.rerun()
        with col_apply:
            if st.button(
                tr("Cockpit Apply Defaults"),
                type="primary",
                use_container_width=True,
            ):
                slug = st.session_state.pop("pending_channel_switch", None)
                if slug:
                    apply_runtime_config(build_runtime_config(slug), slug)
                    st.toast(tr("Cockpit Channel Applied"))
                st.rerun()

    _dialog()


def _show_channel_switch_dialog(target_slug: str, tr: Callable[[str], str]) -> None:
    st.session_state["pending_channel_switch"] = target_slug
    render_channel_switch_dialog(tr)


def handle_channel_selection(
    selected: str,
    previous: str,
    tr: Callable[[str], str],
) -> str:
    """Auto-apply channel defaults or prompt when overrides exist."""
    from app.config import config

    _init_cockpit_session_state()

    if selected == previous:
        return selected

    runtime_current = st.session_state.get("channel_runtime")
    if not runtime_current and previous:
        runtime_current = build_runtime_config(previous)
        st.session_state["channel_runtime"] = runtime_current

    if runtime_current:
        overrides = detect_overrides(runtime_current, collect_form_state())
    else:
        overrides = {}

    if overrides:
        _show_channel_switch_dialog(selected, tr)
        return previous

    apply_runtime_config(build_runtime_config(selected), selected)
    config.ui["active_channel"] = selected
    st.session_state["active_channel"] = selected
    st.toast(tr("Cockpit Channel Applied"))
    return selected


def render_inheritance_badge(
    field_key: str,
    tr: Callable[[str], str],
) -> None:
    runtime = st.session_state.get("channel_runtime") or {}
    if field_key not in runtime:
        return
    overrides = refresh_channel_overrides()
    if field_key in overrides:
        col_badge, col_restore = st.columns([3, 1])
        with col_badge:
            st.caption(f"🔓 {tr('Cockpit Overridden')}")
        with col_restore:
            if st.button("↩", key=f"restore_{field_key}", help=tr("Cockpit Restore From Channel")):
                restore_field_from_channel(field_key, tr)
                st.rerun()
    else:
        st.caption(f"🔒 {tr('Cockpit Inherited From Channel')}")


def _format_summary_value(field_key: str, runtime: dict[str, Any], tr: Callable[[str], str]) -> str:
    from app.services import voice

    value = runtime.get(field_key, "—")
    if field_key == "voice_name":
        if not value or voice.is_no_voice(str(value)):
            return tr("No Voice")
        name = str(value)
        if ":" in name:
            name = name.split(":", 1)[-1]
        return name.replace("Neural", "").replace("-Male", "").replace("-Female", "").strip()
    if field_key == "video_source":
        labels = {
            "collector": tr("Collector (local cache)"),
            "pexels": tr("Pexels"),
            "local": tr("Local file"),
        }
        return labels.get(str(value), str(value))
    if field_key == "bgm_type":
        if value == "profile_random":
            profile = runtime.get("bgm_profile", "")
            return str(profile or tr("Random Background Music by Profile"))
        if not value:
            return tr("No Background Music")
        return str(value)
    if field_key == "subtitle_position":
        positions = {"top": tr("Top"), "center": tr("Center"), "bottom": tr("Bottom")}
        font = runtime.get("font_name", "")
        font_short = str(font).replace(".ttf", "").replace(".ttc", "")
        pos = positions.get(str(value), str(value))
        return f"{font_short} · {pos}"
    return str(value)


def render_subtitle_controls(
    params: Any,
    tr: Callable[[str], str],
    get_all_fonts: Callable[[], list[str]],
    *,
    compact: bool = True,
) -> None:
    """Subtitle settings — compact mode shows position + size only."""
    from app.config import config

    runtime = st.session_state.get("channel_runtime") or {}
    saved_enabled = config.ui.get(
        "subtitle_enabled", runtime.get("subtitle_enabled", True)
    )
    params.subtitle_enabled = st.checkbox(
        tr("Enable Subtitles"),
        value=bool(saved_enabled),
        key="cockpit_subtitle_enabled",
    )
    config.ui["subtitle_enabled"] = params.subtitle_enabled
    render_inheritance_badge("subtitle_enabled", tr)

    subtitle_positions = [
        (tr("Top"), "top"),
        (tr("Center"), "center"),
        (tr("Bottom"), "bottom"),
    ]
    if not compact:
        subtitle_positions.append((tr("Custom"), "custom"))

    saved_subtitle_position = config.ui.get(
        "subtitle_position", runtime.get("subtitle_position", "bottom")
    )
    params.subtitle_position = render_option_cards(
        tr("Position"),
        subtitle_positions,
        saved_subtitle_position,
        "cockpit_subtitle_position",
    )
    config.ui["subtitle_position"] = params.subtitle_position
    render_inheritance_badge("subtitle_position", tr)

    saved_font_size = config.ui.get("font_size", runtime.get("font_size", 60))
    params.font_size = st.slider(
        tr("Font Size"),
        30,
        100,
        int(saved_font_size),
        key="cockpit_font_size",
    )
    config.ui["font_size"] = params.font_size
    render_inheritance_badge("font_size", tr)

    if params.subtitle_position == "custom":
        saved_custom_position = config.ui.get(
            "custom_position", runtime.get("custom_position", 70.0)
        )
        custom_position = st.text_input(
            tr("Custom Position (% from top)"),
            value=str(saved_custom_position),
            key="custom_position_input",
        )
        try:
            params.custom_position = float(custom_position)
            if 0 <= params.custom_position <= 100:
                config.ui["custom_position"] = params.custom_position
            else:
                st.error(tr("Please enter a value between 0 and 100"))
        except ValueError:
            st.error(tr("Please enter a valid number"))

    with st.expander(tr("Cockpit Subtitle Advanced"), expanded=not compact):
        font_names = get_all_fonts()
        saved_font_name = config.ui.get(
            "font_name", runtime.get("font_name", "Roboto-Bold.ttf")
        )
        saved_font_name_index = (
            font_names.index(saved_font_name) if saved_font_name in font_names else 0
        )
        params.font_name = st.selectbox(
            tr("Font"), font_names, index=saved_font_name_index
        )
        config.ui["font_name"] = params.font_name
        render_inheritance_badge("font_name", tr)

        saved_text_fore_color = config.ui.get(
            "text_fore_color", runtime.get("text_fore_color", "#FFFFFF")
        )
        params.text_fore_color = st.color_picker(tr("Font Color"), saved_text_fore_color)
        config.ui["text_fore_color"] = params.text_fore_color

        stroke_cols = st.columns([0.3, 0.7])
        with stroke_cols[0]:
            stroke_default = config.ui.get(
                "stroke_color", runtime.get("stroke_color", "#000000")
            )
            params.stroke_color = st.color_picker(tr("Stroke Color"), stroke_default)
        with stroke_cols[1]:
            stroke_width_default = config.ui.get(
                "stroke_width", runtime.get("stroke_width", 1.5)
            )
            params.stroke_width = st.slider(
                tr("Stroke Width"), 0.0, 10.0, float(stroke_width_default)
            )

        subtitle_bg_cols = st.columns([0.4, 0.6])
        saved_subtitle_background_enabled = config.ui.get(
            "subtitle_background_enabled",
            runtime.get("subtitle_background_enabled", True),
        )
        with subtitle_bg_cols[0]:
            subtitle_background_enabled = st.checkbox(
                tr("Enable Subtitle Background"),
                value=bool(saved_subtitle_background_enabled),
            )
        config.ui["subtitle_background_enabled"] = subtitle_background_enabled
        if subtitle_background_enabled:
            with subtitle_bg_cols[1]:
                saved_subtitle_background_color = config.ui.get(
                    "subtitle_background_color",
                    runtime.get("subtitle_background_color", "#000000"),
                )
                params.text_background_color = st.color_picker(
                    tr("Subtitle Background Color"),
                    saved_subtitle_background_color,
                )
                config.ui["subtitle_background_color"] = params.text_background_color
        else:
            params.text_background_color = False

        saved_rounded = config.ui.get(
            "rounded_subtitle_background",
            runtime.get("rounded_subtitle_background", False),
        )
        params.rounded_subtitle_background = st.checkbox(
            tr("Rounded Subtitle Background"),
            value=bool(saved_rounded) if subtitle_background_enabled else False,
            help=tr("Rounded Subtitle Background Help"),
            disabled=not subtitle_background_enabled,
        )
        if subtitle_background_enabled:
            config.ui["rounded_subtitle_background"] = params.rounded_subtitle_background


def render_progressive_action_bar(
    params: Any,
    tr: Callable[[str], str],
) -> tuple[bool, bool, bool]:
    """Render progressive CTAs. Returns (generate_script, preview, render) button states."""
    has_script = bool(st.session_state.get("video_script", "").strip())
    preview_ready = bool(st.session_state.get("preview_ready"))

    st.markdown('<div class="cockpit-cta-bar">', unsafe_allow_html=True)
    option_cols = st.columns([2, 2, 1, 1])
    with option_cols[2]:
        include_preview_audio = st.checkbox(
            tr("Cockpit Preview Include Audio"), value=False, key="cockpit_preview_audio"
        )
    with option_cols[3]:
        skip_preview = st.checkbox(
            tr("Cockpit Skip Preview Gate"),
            value=st.session_state.get("cockpit_skip_preview", False),
            key="cockpit_skip_preview_cb",
        )
        st.session_state["cockpit_skip_preview"] = skip_preview

    if not has_script:
        generate_script = st.button(
            tr("Cockpit Generate Script"),
            type="primary",
            use_container_width=True,
            key="cockpit_cta_generate_script",
        )
        preview_button = False
        full_button = False
    elif not preview_ready:
        col_secondary, col_primary = st.columns(2)
        with col_secondary:
            generate_script = st.button(
                tr("Cockpit Generate Script"),
                use_container_width=True,
                key="cockpit_cta_regenerate_script",
            )
        with col_primary:
            preview_button = st.button(
                tr("Cockpit Preview"),
                type="primary",
                use_container_width=True,
                key="cockpit_cta_preview",
            )
        full_button = False
    else:
        col_secondary, col_primary = st.columns(2)
        with col_secondary:
            preview_button = st.button(
                tr("Cockpit Preview"),
                use_container_width=True,
                key="cockpit_cta_repreview",
            )
        with col_primary:
            full_button = st.button(
                tr("Cockpit Render Video"),
                type="primary",
                use_container_width=True,
                key="cockpit_cta_render",
            )
        generate_script = False

    st.markdown("</div>", unsafe_allow_html=True)
    return generate_script, preview_button, full_button, include_preview_audio, skip_preview


def render_channel_summary(
    runtime: dict[str, Any],
    tr: Callable[[str], str],
) -> None:
    """Compact sidebar summary of inherited channel settings."""
    channel_name = runtime.get("name") or runtime.get("slug", "—")
    st.markdown(f"**{channel_name}**")
    st.caption(tr("Cockpit Using Channel Defaults"))

    summary_fields = [
        ("video_source", tr("Video Source")),
        ("voice_name", tr("Speech Synthesis")),
        ("video_aspect", tr("Video Ratio")),
        ("bgm_type", tr("Background Music")),
        ("subtitle_position", tr("Subtitle Settings")),
        ("target_duration", tr("Cockpit Target Duration")),
    ]
    for field_key, label in summary_fields:
        if field_key == "target_duration":
            value = runtime.get("target_duration") or "—"
            st.markdown(
                f'<div class="cockpit-summary-row">'
                f'<span>✓ {label}</span>'
                f'<span class="cockpit-inherited-badge">🔒 {value}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            continue
        display = _format_summary_value(field_key, runtime, tr)
        overrides = st.session_state.get("channel_overrides", set())
        badge = "🔓" if field_key in overrides else "🔒"
        st.markdown(
            f'<div class="cockpit-summary-row">'
            f"<span>✓ {label}</span>"
            f'<span class="cockpit-inherited-badge">{badge} {display}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )


def render_pipeline_step_summary(
    step: str,
    runtime: dict[str, Any],
    tr: Callable[[str], str],
    *,
    advanced_mode: bool,
) -> None:
    """Content for Media / Voice / Subtitles / Export step sections."""
    step_fields = {
        "media": [
            ("video_source", tr("Video Source")),
            ("video_aspect", tr("Video Ratio")),
            ("video_concat_mode", tr("Video Concat Mode")),
            ("video_clip_duration", tr("Clip Duration")),
            ("video_count", tr("Cockpit Video Count")),
        ],
        "voice": [
            ("voice_name", tr("Speech Synthesis")),
            ("voice_volume", tr("Speech Volume")),
            ("voice_rate", tr("Speech Rate")),
            ("bgm_type", tr("Background Music")),
        ],
        "subtitles": [
            ("subtitle_position", tr("Position")),
            ("font_name", tr("Font")),
            ("font_size", tr("Font Size")),
            ("text_fore_color", tr("Font Color")),
        ],
        "export": [
            ("target_duration", tr("Cockpit Target Duration")),
            ("mode", tr("Cockpit Channel Mode")),
        ],
    }
    fields = step_fields.get(step, [])
    if not runtime:
        st.info(tr("Cockpit Step No Channel"))
        return

    st.caption(tr("Cockpit Using Channel Defaults"))
    for field_key, label in fields:
        if field_key in {"voice_volume", "voice_rate", "font_size", "video_clip_duration", "video_count"}:
            display = str(runtime.get(field_key, "—"))
        elif field_key == "target_duration":
            display = str(runtime.get("target_duration") or "—")
        elif field_key == "mode":
            display = str(runtime.get("mode") or "faceless")
        elif field_key == "video_concat_mode":
            modes = {"sequential": tr("Sequential"), "random": tr("Random")}
            display = modes.get(str(runtime.get(field_key, "")), str(runtime.get(field_key, "—")))
        elif field_key == "text_fore_color":
            display = str(runtime.get(field_key, "—"))
        else:
            display = _format_summary_value(field_key, runtime, tr)
        st.markdown(f"- **{label}:** {display}")

    if not advanced_mode:
        st.info(tr("Cockpit Step Open Advanced"))
    else:
        st.caption(tr("Cockpit Step Edit In Sidebar"))


def render_assembly_panel(
    tr: Callable[[str], str],
    runtime: dict[str, Any],
    *,
    advanced_mode: bool,
) -> None:
    """Montagem step — checklist, settings summary and script preview."""
    has_script = bool(str(st.session_state.get("video_script", "") or "").strip())
    has_terms = bool(str(st.session_state.get("video_terms", "") or "").strip())
    preview_ready = bool(st.session_state.get("preview_ready"))

    st.markdown(f"**{tr('Cockpit Assembly Checklist')}**")
    for label, done in [
        (tr("Cockpit Step Script"), has_script),
        (tr("Video Keywords"), has_terms),
        (tr("Cockpit Assembly Preview"), preview_ready),
    ]:
        st.markdown(f"{'✅' if done else '⬜'} {label}")

    if not has_script:
        st.info(tr("Cockpit Assembly Need Script"))
        return

    if preview_ready:
        st.success(tr("Cockpit Preview Ready"))
    else:
        st.warning(tr("Cockpit Assembly Need Preview"))

    st.markdown(f"**{tr('Cockpit Assembly Settings')}**")
    if runtime:
        render_channel_summary(runtime, tr)
    elif not advanced_mode:
        st.info(tr("Cockpit Step No Channel"))
    else:
        st.caption(tr("Cockpit Step Edit In Sidebar"))

    with st.expander(tr("Cockpit Step Script"), expanded=False):
        st.text(st.session_state.get("video_script", ""))

    if has_terms:
        with st.expander(tr("Video Keywords"), expanded=False):
            st.text(st.session_state.get("video_terms", ""))

    st.caption(tr("Cockpit Assembly CTA Hint"))


def _llm_readiness(tr: Callable[[str], str]) -> tuple[str, str]:
    import os

    from app.config import config

    provider = str(config.app.get("llm_provider", "") or "").strip().lower()
    if not provider:
        return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Provider")

    if provider == "litellm":
        model = str(config.app.get("litellm_model_name", "") or "").strip()
        if model:
            return tr("Cockpit Status Ready"), provider
        return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Model")

    if provider == "anthropic":
        import os

        model = str(config.app.get("anthropic_model_name", "") or "").strip()
        api_key = str(
            config.app.get("anthropic_api_key")
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        ).strip()
        if not model:
            return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Model")
        if api_key:
            return tr("Cockpit Status Ready"), provider
        return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Key")

    if provider == "bedrock":
        model = str(config.app.get("bedrock_model_name", "") or "").strip()
        region = str(config.app.get("bedrock_region", "") or "").strip()
        if not model:
            return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Model")
        if not region:
            return tr("Cockpit Status Blocked"), tr("Cockpit LLM Missing Region")

        from app.services.llm import (
            is_bedrock_mantle_responses_model,
            is_valid_bedrock_bearer_token,
            looks_like_aws_access_key_id,
            looks_like_bedrock_iam_username,
        )

        if is_bedrock_mantle_responses_model(model):
            mantle_regions = {"us-east-2", "us-west-2"}
            if region not in mantle_regions:
                return tr("Cockpit Status Blocked"), tr("Cockpit Bedrock Mantle Region")

        bedrock_key = str(
            config.app.get("bedrock_api_key")
            or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            or ""
        ).strip()
        if bedrock_key:
            if looks_like_bedrock_iam_username(bedrock_key):
                return tr("Cockpit Status Blocked"), tr("Cockpit Bedrock Key IAM Username")
            if looks_like_aws_access_key_id(bedrock_key):
                return tr("Cockpit Status Blocked"), tr("Cockpit Bedrock Key Wrong Field")
            if not is_valid_bedrock_bearer_token(bedrock_key):
                return tr("Cockpit Status Blocked"), tr("Cockpit Bedrock Key Invalid Prefix")
            return tr("Cockpit Status Ready"), provider

        if is_bedrock_mantle_responses_model(model):
            return tr("Cockpit Status Blocked"), tr("Cockpit Bedrock Mantle Key Required")

        has_config_creds = bool(
            config.app.get("bedrock_aws_access_key_id")
            and config.app.get("bedrock_aws_secret_access_key")
        )
        if has_config_creds or os.environ.get("AWS_ACCESS_KEY_ID"):
            return tr("Cockpit Status Ready"), provider
        return tr("Cockpit Status Ready"), tr("Cockpit LLM IAM Role")

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


def _provider_status_kind(status: str, tr: Callable[[str], str]) -> str:
    if status == tr("Cockpit Status Ready"):
        return "ready"
    if status == tr("Cockpit Status Blocked"):
        return "blocked"
    return "skipped"


_PROVIDER_ICONS: dict[str, str] = {
    "Cockpit Provider LLM": "🧠",
    "Cockpit Provider Collector": "📦",
    "Cockpit Provider TTS": "🎙️",
    "Cockpit Provider FFmpeg": "⚙️",
    "Cockpit Provider BGM": "🎵",
}


def render_provider_center(
    video_source: str,
    voice_name: str,
    tr: Callable[[str], str],
    *,
    expanded: bool | None = None,
) -> None:
    """Readiness grid with prominent provider cards."""
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

    render_section_title(tr("Cockpit Provider Center"))
    with st.expander(tr("Cockpit Provider Center Details"), expanded=expanded):
        card_html = ['<div class="cockpit-provider-grid">']
        for label, status, detail in checks:
            icon = _PROVIDER_ICONS.get(label, "●")
            kind = _provider_status_kind(status, tr)
            dot = "🟢" if kind == "ready" else ("🔴" if kind == "blocked" else "⚪")
            card_html.append(
                f'<div class="cockpit-provider-card cockpit-provider-{kind}">'
                f'<div class="cockpit-provider-icon">{icon}</div>'
                f'<div class="cockpit-provider-name">{label}</div>'
                f'<div class="cockpit-provider-detail">{detail or "—"}</div>'
                f'<div class="cockpit-provider-status">{dot} {status}</div>'
                f"</div>"
            )
        card_html.append("</div>")
        st.markdown("".join(card_html), unsafe_allow_html=True)


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


def render_scene_breakdown(
    script: str,
    structure: list[str] | None,
    tr: Callable[[str], str],
) -> None:
    from app.services.scene_parser import parse_script_scenes

    scenes = parse_script_scenes(script, structure or None)
    if not scenes:
        return
    with st.expander(tr("Cockpit Scene Breakdown"), expanded=False):
        for index, scene in enumerate(scenes, start=1):
            role = scene.get("role", "scene")
            st.markdown(f"**{index}. {role.upper()}**")
            st.caption(scene.get("text", ""))


def render_bgm_audit_warning(
    task_id: str,
    bgm_type: str,
    tr: Callable[[str], str],
) -> None:
    from app.services.bgm_audit import read_bgm_failure

    if not (bgm_type or "").strip():
        return
    failure = read_bgm_failure(task_id)
    if not failure:
        return
    st.warning(
        f"{tr('Cockpit BGM Skipped')}: {failure.get('reason', tr('Cockpit BGM Unknown Reason'))}"
    )


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
        from app.models.schema import format_collector_keywords_for_ui

        if isinstance(terms, str):
            terms_text = terms
        else:
            terms_text = format_collector_keywords_for_ui(
                [keyword.model_dump() for keyword in terms.keywords]
            )

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
    from datetime import datetime

    st.session_state["last_preview_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state["cockpit_active_step"] = 4
    st.success(tr("Cockpit Preview Ready"))
    return True


COCKPIT_CSS = """
<style>
/* ── Layout & scale ── */
section.main .block-container {
    max-width: 100% !important;
    padding-top: 0.65rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
section.main [data-testid="stTabs"] {
    margin-top: 0.25rem;
}
section.main [data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.35rem;
    min-height: 2.25rem;
}

/* ── App header (compact) ── */
.cockpit-app-header {
    margin-bottom: 0;
    line-height: 1.2;
}
.cockpit-app-brand {
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #f8fafc;
}
.cockpit-app-version {
    font-size: 0.8rem;
    color: #64748b;
    margin-left: 0.5rem;
    font-weight: 500;
}

/* ── Channel inline ── */
.cockpit-channel-inline {
    font-size: 0.95rem;
    color: #cbd5e1;
    padding: 0.35rem 0 0.15rem 0;
    line-height: 1.35;
}
.cockpit-channel-inline strong {
    color: #f8fafc;
}

/* ── Section hierarchy ── */
.cockpit-section-title {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.25;
    margin: 0 0 1rem 0;
    color: #f8fafc;
    letter-spacing: -0.02em;
}
.cockpit-inspector-settings-title {
    margin-top: 1.5rem;
    margin-bottom: 0.85rem;
    font-size: 1.25rem;
}

/* ── Pipeline track ── */
.cockpit-pipeline-track {
    margin: 0.65rem 0 1.25rem 0;
    display: flex;
}
.cockpit-pipeline-track > div[data-testid="stHorizontalBlock"] {
    gap: 0.35rem;
    align-items: stretch;
}
.cockpit-pipeline-track [data-testid="column"] {
    position: relative;
}
.cockpit-pipeline-track [data-testid="column"]:not(:last-child)::after {
    content: "────";
    position: absolute;
    right: -0.45rem;
    top: 50%;
    transform: translateY(-50%);
    color: #475569;
    font-size: 0.65rem;
    letter-spacing: -1px;
    z-index: 0;
    pointer-events: none;
    opacity: 0.85;
}
.cockpit-pipeline-track [data-testid="column"] button {
    position: relative;
    z-index: 1;
    min-height: 52px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 0.5rem 0.65rem !important;
    background: rgba(15, 23, 42, 0.65) !important;
    border: 2px solid rgba(71, 85, 105, 0.45) !important;
    white-space: nowrap;
}
.cockpit-pipeline-track [data-testid="column"] button[data-testid="stBaseButton-primary"] {
    border-color: rgba(251, 146, 60, 0.85) !important;
    background: rgba(251, 146, 60, 0.14) !important;
    box-shadow: 0 0 0 1px rgba(251, 146, 60, 0.25), 0 4px 16px rgba(251, 146, 60, 0.15) !important;
}
.cockpit-pipeline-track [data-testid="column"] button[data-testid="stBaseButton-secondary"] {
    opacity: 0.9;
}

/* ── Production header badges ── */
.cockpit-prod-header {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem 2rem;
    padding: 1rem 1.15rem;
    margin: 0 0 1.25rem 0;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.92));
    border: 1px solid rgba(99, 102, 241, 0.35);
    box-shadow: 0 6px 28px rgba(0, 0, 0, 0.2);
}
.cockpit-prod-group-label {
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    color: #64748b;
    margin-bottom: 0.45rem;
    text-transform: uppercase;
}
.cockpit-prod-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
}
.cockpit-badge {
    display: inline-block;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    font-size: 0.9rem;
    font-weight: 600;
    color: #e2e8f0;
    background: rgba(51, 65, 85, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.25);
}
.cockpit-badge-accent {
    border-color: rgba(129, 140, 248, 0.55);
    background: rgba(99, 102, 241, 0.18);
    color: #e0e7ff;
}
.cockpit-badge-metric {
    border-color: rgba(74, 222, 128, 0.35);
    background: rgba(74, 222, 128, 0.1);
    color: #bbf7d0;
}

/* ── Ops bar ── */
.cockpit-ops-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem 1.5rem;
    font-size: 0.85rem;
    color: #94a3b8;
    padding: 0.15rem 0 0.35rem 0;
    margin-bottom: 0.35rem;
}

/* ── Inspector panel (+15%) ── */
.cockpit-inspector-panel {
    font-size: 1rem;
}
.cockpit-inspector-panel label,
.cockpit-inspector-panel .stCaption,
.cockpit-inspector-panel p {
    font-size: 0.95rem !important;
}
.cockpit-inspector-panel [data-testid="stWidgetLabel"] p {
    font-size: 0.95rem !important;
}
.cockpit-context-panel {
    margin-bottom: 0.75rem;
}
.cockpit-context-panel-title {
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 0.55rem;
}
.cockpit-context-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
}
.cockpit-ctx-chip {
    display: inline-flex;
    flex-direction: column;
    gap: 0.1rem;
    padding: 0.4rem 0.65rem;
    border-radius: 8px;
    background: rgba(30, 41, 59, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.18);
    min-width: 4.5rem;
}
.cockpit-ctx-chip-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #64748b;
}
.cockpit-ctx-chip-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: #f1f5f9;
    line-height: 1.25;
}

/* ── Provider cards ── */
.cockpit-provider-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11.5rem, 1fr));
    gap: 1rem;
    margin: 0.75rem 0 0.5rem 0;
}
.cockpit-provider-card {
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 12px;
    padding: 1.15rem 1rem;
    background: rgba(30, 41, 59, 0.5);
    min-height: 9rem;
    display: flex;
    flex-direction: column;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.cockpit-provider-card:hover {
    border-color: rgba(148, 163, 184, 0.38);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}
.cockpit-provider-ready {
    border-color: rgba(74, 222, 128, 0.28);
}
.cockpit-provider-blocked {
    border-color: rgba(248, 113, 113, 0.35);
}
.cockpit-provider-icon {
    font-size: 2rem;
    line-height: 1;
    margin-bottom: 0.55rem;
}
.cockpit-provider-name {
    font-size: 0.75rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 700;
    margin-bottom: 0.35rem;
}
.cockpit-provider-detail {
    font-size: 1rem;
    font-weight: 600;
    color: #f1f5f9;
    line-height: 1.35;
    margin-bottom: auto;
    padding-bottom: 0.65rem;
    word-break: break-word;
}
.cockpit-provider-status {
    font-size: 0.9rem;
    font-weight: 700;
    margin-top: 0.35rem;
}
.cockpit-provider-ready .cockpit-provider-status { color: #4ade80; }
.cockpit-provider-blocked .cockpit-provider-status { color: #f87171; }
.cockpit-provider-skipped .cockpit-provider-status { color: #94a3b8; }

/* ── Document workspace (left column) ── */
.cockpit-doc-workspace {
    padding-right: 0.5rem;
}
.cockpit-doc-stage {
    margin-bottom: 0.85rem;
}
.cockpit-doc-title {
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #f8fafc;
    padding-bottom: 0.55rem;
    border-bottom: 2px solid rgba(99, 102, 241, 0.45);
}
.cockpit-doc-divider {
    height: 1px;
    margin: 1.35rem 0;
    background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.35), transparent);
}
.cockpit-doc-section-label {
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 0.55rem;
}
.cockpit-doc-workspace [data-testid="stTextArea"] textarea {
    min-height: 420px !important;
    font-size: 16px !important;
    line-height: 1.55 !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    background: rgba(15, 23, 42, 0.35) !important;
}
.cockpit-doc-workspace [data-testid="stTextInput"] input {
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    background: rgba(15, 23, 42, 0.35) !important;
}

/* ── Important secondary buttons ── */
.cockpit-btn-important button[data-testid="stBaseButton-secondary"] {
    min-height: 46px !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    border-color: rgba(129, 140, 248, 0.55) !important;
    background: rgba(99, 102, 241, 0.12) !important;
    color: #e0e7ff !important;
}
.cockpit-btn-important button[data-testid="stBaseButton-secondary"]:hover {
    border-color: rgba(165, 180, 252, 0.75) !important;
    background: rgba(99, 102, 241, 0.22) !important;
}

/* ── Preview approval gate ── */
.cockpit-approval-gate {
    margin: 0.5rem 0 1rem 0;
    padding: 0.85rem 1rem;
    border-radius: 10px;
    background: rgba(15, 23, 42, 0.45);
    border: 1px solid rgba(148, 163, 184, 0.15);
}
.cockpit-check-row {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.4rem 0;
    font-size: 1rem;
    font-weight: 500;
}
.cockpit-check-done {
    color: #bbf7d0;
}
.cockpit-check-pending {
    color: #94a3b8;
}
.cockpit-check-icon {
    font-size: 1.05rem;
    font-weight: 700;
    min-width: 1.25rem;
}
.cockpit-approval-divider {
    height: 1px;
    margin: 0.75rem 0 0.25rem 0;
    background: rgba(148, 163, 184, 0.25);
}

/* ── Collector stats ── */
.cockpit-collector-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr));
    gap: 0.85rem;
    margin: 0.5rem 0 1rem 0;
}
.cockpit-collector-stat {
    padding: 0.85rem 0.9rem;
    border-radius: 10px;
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(148, 163, 184, 0.2);
    min-height: 6.5rem;
}
.cockpit-collector-stat-icon {
    font-size: 1.35rem;
    margin-bottom: 0.25rem;
}
.cockpit-collector-stat-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #64748b;
}
.cockpit-collector-stat-value {
    font-size: 1rem;
    font-weight: 700;
    color: #f1f5f9;
    margin: 0.25rem 0 0.15rem 0;
    line-height: 1.3;
}
.cockpit-collector-stat-hint {
    font-size: 0.78rem;
    color: #94a3b8;
    line-height: 1.3;
}

/* ── Result cards ── */
.cockpit-result-card {
    padding: 0.85rem 0;
    margin-bottom: 0.65rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}
.cockpit-result-card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #e2e8f0;
    margin-bottom: 0.55rem;
}
.cockpit-result-card button[data-testid="stBaseButton-secondary"] {
    min-height: 2.35rem !important;
    font-size: 0.85rem !important;
}

/* ── Preview / CTA ── */
.cockpit-card-group-label {
    font-size: 1.05rem;
    font-weight: 700;
    margin: 0.5rem 0 0.75rem 0;
    color: #e2e8f0;
}
.cockpit-card-group-label + div[data-testid="stHorizontalBlock"] button {
    min-height: 3.25rem;
    border-radius: 0.75rem;
    font-weight: 600;
    font-size: 0.9375rem;
}
.cockpit-summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 0;
    font-size: 0.9375rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}
.cockpit-inherited-badge {
    color: #94a3b8;
    font-size: 0.875rem;
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 55%;
}
.cockpit-cta-bar {
    margin: 0.85rem 0 1rem 0;
}
.cockpit-cta-bar button[data-testid="stBaseButton-primary"] {
    min-height: 3.5rem;
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}

/* ── Form inputs ── */
section.main [data-testid="stTextInput"] input,
section.main [data-testid="stTextArea"] textarea,
section.main [data-testid="stNumberInput"] input {
    min-height: 48px !important;
    font-size: 16px !important;
}
section.main [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    min-height: 48px !important;
    font-size: 16px !important;
}
section.main [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    min-height: 48px !important;
    font-size: 16px !important;
}

/* ── Expander headers in cockpit ── */
section.main [data-testid="stExpander"] summary {
    font-size: 0.9375rem !important;
    font-weight: 600 !important;
    color: #94a3b8 !important;
}
section.main [data-testid="stExpander"] summary:hover {
    color: #cbd5e1 !important;
}
</style>
"""


def _default_active_step() -> int:
    if st.session_state.get("last_render_task_id"):
        return 5
    if st.session_state.get("preview_ready"):
        return 4
    if st.session_state.get("video_script"):
        return 1
    return 0


def render_stepper(tr: Callable[[str], str], active_index: int | None = None) -> None:
    """Deprecated — use render_pipeline_nav."""
    render_pipeline_nav(tr)


def render_step_section(
    step_index: int,
    title: str,
    render_content: Callable[[], None],
) -> None:
    """Deprecated — single-panel editor replaces expanders."""
    active = st.session_state.get("cockpit_active_step", 0)
    if step_index == active:
        render_content()
