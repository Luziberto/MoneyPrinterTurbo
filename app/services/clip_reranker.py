"""Clip reranking hooks (SigLIP planned; score-based fallback today)."""

from __future__ import annotations

import os
from typing import Iterable

from loguru import logger

from app.models.schema import CollectorSelectedClip


def get_reranker_kind() -> str:
    return (os.getenv("MPT_RERANKER") or "none").strip().lower() or "none"


def rerank_collector_clips(
    clips: Iterable[CollectorSelectedClip],
    *,
    keyword: str = "",
) -> list[CollectorSelectedClip]:
    """Reorder collector clips for a keyword/segment."""
    items = list(clips)
    if len(items) <= 1:
        return items

    kind = get_reranker_kind()
    if kind == "none":
        return items
    if kind == "siglip":
        try:
            from app.services import siglip_reranker

            return siglip_reranker.rerank_by_text(items, keyword)
        except ImportError:
            logger.warning(
                "MPT_RERANKER=siglip requested but optional dependencies are missing; "
                "falling back to collector score ordering"
            )

    return sorted(
        items,
        key=lambda clip: (
            clip.visual_score,
            clip.retrieval_score,
            clip.score,
        ),
        reverse=True,
    )
