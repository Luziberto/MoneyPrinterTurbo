"""Server-side keyword helpers for the cockpit API.

Distinct from webui/cockpit_keywords.py, which is Streamlit-widget-bound.
This module has no UI dependency — it only converts between
NormalizedCollectorKeywords (LLM output shape) and WorkspaceKeywords.
"""

from __future__ import annotations

from app.models.schema import NormalizedCollectorKeywords, WorkspaceKeywords


def normalized_to_workspace_keywords(
    normalized: NormalizedCollectorKeywords,
) -> WorkspaceKeywords:
    return WorkspaceKeywords(
        terms=list(normalized.keywords),
        has_explicit_weights=normalized.has_explicit_weights,
    )
