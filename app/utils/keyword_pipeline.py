"""Derive collector keywords from script paragraphs (merge, dedupe, rank)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.schema import CollectorKeyword


def split_script_paragraphs(
    video_script: str,
    expected: int | None = None,
) -> list[str]:
    text = str(video_script or "").strip()
    if not text:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) <= 1 and "\n" in text:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) > 1:
            paragraphs = lines

    if not paragraphs:
        return [text]

    if expected and expected > 0:
        if len(paragraphs) > expected:
            paragraphs = paragraphs[:expected]
        elif len(paragraphs) < expected and len(paragraphs) == 1:
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", paragraphs[0])
                if sentence.strip()
            ]
            if len(sentences) >= expected:
                chunk_size = max(1, len(sentences) // expected)
                grouped: list[str] = []
                for index in range(0, len(sentences), chunk_size):
                    chunk = " ".join(sentences[index : index + chunk_size]).strip()
                    if chunk:
                        grouped.append(chunk)
                if len(grouped) >= expected:
                    paragraphs = grouped[:expected]

    return paragraphs


def paragraph_keyword_weight(paragraph_index: int, keyword_index: int) -> float:
    """Earlier paragraphs and earlier keywords within a paragraph rank higher."""
    position = (paragraph_index * 3) + keyword_index
    return max(0.4, round(1.0 - (position * 0.08), 2))


def merge_dedupe_rank_keywords(keywords: list[CollectorKeyword]) -> list[CollectorKeyword]:
    from app.models.schema import CollectorKeyword

    best_by_term: dict[str, CollectorKeyword] = {}
    for keyword in keywords:
        term = str(keyword.term or "").strip()
        if not term:
            continue
        key = term.casefold()
        current = best_by_term.get(key)
        if current is None or keyword.weight > current.weight:
            best_by_term[key] = keyword.model_copy(update={"term": term})

    ranked = sorted(best_by_term.values(), key=lambda item: item.weight, reverse=True)
    return ranked


def apply_paragraph_weights(
    paragraph_groups: list[list[CollectorKeyword]],
) -> list[CollectorKeyword]:
    weighted: list[CollectorKeyword] = []
    for paragraph_index, group in enumerate(paragraph_groups):
        for keyword_index, keyword in enumerate(group):
            weight = paragraph_keyword_weight(paragraph_index, keyword_index)
            weighted.append(keyword.model_copy(update={"weight": weight}))
    return merge_dedupe_rank_keywords(weighted)
