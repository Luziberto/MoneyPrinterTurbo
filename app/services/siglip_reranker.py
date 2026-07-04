"""Optional SigLIP reranker (spec 022). Install torch/transformers to enable."""

from __future__ import annotations

from app.models.schema import CollectorSelectedClip
from app.services.clip_reranker import get_reranker_kind


def rerank_by_text(
    clips: list[CollectorSelectedClip],
    keyword: str,
) -> list[CollectorSelectedClip]:
    """Placeholder until local SigLIP model is wired."""
    del keyword
    if get_reranker_kind() != "siglip":
        return clips
    return sorted(
        clips,
        key=lambda clip: (
            clip.visual_score,
            clip.retrieval_score,
            clip.score,
        ),
        reverse=True,
    )
