"""Lightweight script scene splitter for intro/body/CTA editorial flows."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_STRUCTURE = ("intro", "body", "cta")

_ROLE_ALIASES = {
    "intro": ("intro", "hook", "abertura", "opening"),
    "body": ("body", "corpo", "main", "development"),
    "cta": ("cta", "call to action", "fechamento", "close", "closing"),
}


def _split_paragraphs(script: str) -> list[str]:
    chunks = [part.strip() for part in re.split(r"\n\s*\n", script or "")]
    return [chunk for chunk in chunks if chunk]


def _match_labeled_paragraph(paragraph: str) -> tuple[str | None, str]:
    match = re.match(
        r"^\s*(?:\[|\()?(intro|hook|body|corpo|cta|fechamento|abertura)\s*[:)\]-]\s*(.*)$",
        paragraph,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None, paragraph
    role_key = match.group(1).lower()
    for role, aliases in _ROLE_ALIASES.items():
        if role_key in aliases:
            return role, match.group(2).strip()
    return None, paragraph


def parse_script_scenes(
    script: str,
    structure: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Split a script into editorial scenes without LLM calls."""
    roles = tuple(structure or DEFAULT_STRUCTURE)
    paragraphs = _split_paragraphs(script)
    if not paragraphs:
        return []

    labeled: list[dict[str, Any]] = []
    unlabeled: list[str] = []
    for paragraph in paragraphs:
        role, text = _match_labeled_paragraph(paragraph)
        if role and text:
            labeled.append({"role": role, "text": text})
        else:
            unlabeled.append(paragraph)

    if labeled:
        return labeled

    if len(unlabeled) >= len(roles):
        return [
            {"role": roles[index], "text": unlabeled[index]}
            for index in range(len(roles))
        ]

    if len(unlabeled) == 1:
        return [{"role": roles[0], "text": unlabeled[0]}]

    return [
        {"role": roles[min(index, len(roles) - 1)], "text": text}
        for index, text in enumerate(unlabeled)
    ]
