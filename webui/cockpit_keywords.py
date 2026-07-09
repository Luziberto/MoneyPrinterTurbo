"""Structured collector keywords editor for the cockpit."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from app.models.schema import (
    CollectorKeyword,
    NormalizedCollectorKeywords,
    normalize_collector_keywords,
)

VIDEO_TERMS_KEY = "video_terms_keywords"
LEGACY_VIDEO_TERMS_KEY = "video_terms"
EDITOR_WIDGET_KEY = "video_terms_editor"
# Keeps visual_intent/alternatives/required_concepts/optional_concepts per term
# so the term+weight grid can round-trip edits without discarding the visual package.
PACKAGE_STORE_KEY = "video_terms_packages"


def _package_extras(term: str) -> dict[str, Any]:
    store = st.session_state.get(PACKAGE_STORE_KEY) or {}
    extras = store.get(term)
    return extras if isinstance(extras, dict) else {}


def _update_package_store(keywords: list[CollectorKeyword]) -> None:
    store = dict(st.session_state.get(PACKAGE_STORE_KEY) or {})
    for keyword in keywords:
        if not keyword.term:
            continue
        store[keyword.term] = {
            "visual_intent": keyword.visual_intent,
            "alternatives": list(keyword.alternatives),
            "required_concepts": list(keyword.required_concepts),
            "optional_concepts": list(keyword.optional_concepts),
        }
    st.session_state[PACKAGE_STORE_KEY] = store


def _clamp_weight(value: Any) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        weight = 1.0
    return max(0.0, min(1.0, weight))


def _rows_from_normalized(normalized: NormalizedCollectorKeywords) -> list[dict[str, Any]]:
    return [
        {"term": keyword.term, "weight": float(keyword.weight)}
        for keyword in normalized.keywords
        if keyword.term
    ]


def _coerce_editor_rows(value: Any) -> list[dict[str, Any]]:
    """Normalize st.data_editor output (often a DataFrame) to row dicts."""
    if value is None:
        return []
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    try:
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            records = value.to_dict(orient="records")
            return [row for row in records if isinstance(row, dict)]
    except ImportError:
        pass
    return []


def _normalized_from_rows(rows: list[dict[str, Any]] | None) -> NormalizedCollectorKeywords:
    keywords: list[CollectorKeyword] = []
    has_weights = False
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        term = str(row.get("term", "") or "").strip()
        if not term:
            continue
        weight = _clamp_weight(row.get("weight", 1.0))
        if weight != 1.0:
            has_weights = True
        # Re-attach the visual package saved for this term (if any); a term typed
        # or renamed by hand in the grid falls back to compat defaults.
        extras = _package_extras(term)
        keywords.append(
            CollectorKeyword(
                term=term,
                weight=weight,
                visual_intent=str(extras.get("visual_intent", "") or ""),
                alternatives=list(extras.get("alternatives") or []),
                required_concepts=list(extras.get("required_concepts") or term.split()),
                optional_concepts=list(extras.get("optional_concepts") or []),
            )
        )
    return NormalizedCollectorKeywords(
        keywords=keywords,
        has_explicit_weights=has_weights or any(k.weight != 1.0 for k in keywords),
    )


def ensure_video_terms_session_state() -> list[dict[str, Any]]:
    """Load structured keywords from session, migrating legacy comma-separated text once."""
    if VIDEO_TERMS_KEY in st.session_state:
        rows = st.session_state.get(VIDEO_TERMS_KEY)
        if isinstance(rows, list):
            return rows

    legacy = st.session_state.get(LEGACY_VIDEO_TERMS_KEY, "")
    normalized = normalize_collector_keywords(legacy)
    rows = _rows_from_normalized(normalized)
    st.session_state[VIDEO_TERMS_KEY] = rows
    return rows


def get_normalized_video_terms() -> NormalizedCollectorKeywords:
    rows = ensure_video_terms_session_state()
    if EDITOR_WIDGET_KEY in st.session_state:
        rows = _coerce_editor_rows(st.session_state.get(EDITOR_WIDGET_KEY)) or rows
    return _normalized_from_rows(rows)


def set_normalized_video_terms(normalized: NormalizedCollectorKeywords) -> None:
    rows = _rows_from_normalized(normalized)
    st.session_state[VIDEO_TERMS_KEY] = rows
    st.session_state[LEGACY_VIDEO_TERMS_KEY] = ""
    _update_package_store(normalized.keywords)
    # Widget keys are owned by Streamlit; clear so the editor re-inits from VIDEO_TERMS_KEY.
    st.session_state.pop(EDITOR_WIDGET_KEY, None)


def count_video_terms() -> int:
    return len(get_normalized_video_terms().keywords)


def has_video_terms() -> bool:
    return count_video_terms() > 0


def payloads_for_params() -> list[dict[str, Any]]:
    return [keyword.model_dump() for keyword in get_normalized_video_terms().keywords]


def format_for_display() -> str:
    from app.models.schema import format_collector_keywords_for_ui

    return format_collector_keywords_for_ui(payloads_for_params())


def render_keywords_editor(tr: Callable[[str], str]) -> NormalizedCollectorKeywords:
    """Editable keyword × weight table."""
    rows = ensure_video_terms_session_state()
    edited = st.data_editor(
        rows,
        column_config={
            "term": st.column_config.TextColumn(
                tr("Cockpit Keyword Term"),
                required=True,
                width="large",
            ),
            "weight": st.column_config.NumberColumn(
                tr("Cockpit Keyword Weight"),
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                format="%.2f",
                width="small",
            ),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=EDITOR_WIDGET_KEY,
    )
    sanitized = _normalized_from_rows(_coerce_editor_rows(edited))
    rows_out = _rows_from_normalized(sanitized)
    st.session_state[VIDEO_TERMS_KEY] = rows_out
    return sanitized
