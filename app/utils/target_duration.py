"""Parse channel target_duration strings and derive script timing."""

from __future__ import annotations

import re

SECONDS_PER_PARAGRAPH = 25
DURATION_STEP_SECONDS = 10
MIN_DURATION_SECONDS = 10
MAX_DURATION_SECONDS = 300
DEFAULT_TARGET_DURATION = "60-90"

_DURATION_TOKEN_RE = re.compile(r"\d+")


def duration_second_options(
    *,
    min_seconds: int = MIN_DURATION_SECONDS,
    max_seconds: int = MAX_DURATION_SECONDS,
    step: int = DURATION_STEP_SECONDS,
) -> list[int]:
    return list(range(min_seconds, max_seconds + 1, step))


def parse_target_duration(raw: str | None) -> tuple[int, int]:
    """Parse values like ``60-90``, ``60``, or ``60s-90s`` into (min, max) seconds."""
    text = str(raw or "").strip().lower().replace("s", "")
    if not text:
        return _parse_target_duration(DEFAULT_TARGET_DURATION)

    numbers = [int(token) for token in _DURATION_TOKEN_RE.findall(text)]
    if not numbers:
        return _parse_target_duration(DEFAULT_TARGET_DURATION)

    min_seconds = _clamp_duration(numbers[0])
    max_seconds = _clamp_duration(numbers[1] if len(numbers) > 1 else numbers[0])
    if max_seconds < min_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    return min_seconds, max_seconds


def format_target_duration(min_seconds: int, max_seconds: int) -> str:
    min_seconds = _clamp_duration(min_seconds)
    max_seconds = _clamp_duration(max_seconds)
    if max_seconds < min_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    if min_seconds == max_seconds:
        return str(min_seconds)
    return f"{min_seconds}-{max_seconds}"


def midpoint_seconds(min_seconds: int, max_seconds: int) -> int:
    lo, hi = parse_target_duration(format_target_duration(min_seconds, max_seconds))
    return (lo + hi) // 2


def paragraph_number_from_target_duration(raw: str | None) -> int:
    """Derive script paragraphs from channel duration (midpoint / 25s per paragraph)."""
    min_seconds, max_seconds = parse_target_duration(raw)
    mid = midpoint_seconds(min_seconds, max_seconds)
    paragraphs = round(mid / SECONDS_PER_PARAGRAPH)
    return max(1, min(10, paragraphs))


def duration_seconds_from_target_duration(raw: str | None) -> int:
    """Single spoken-duration target for polish / narration hints."""
    min_seconds, max_seconds = parse_target_duration(raw)
    return max(30, midpoint_seconds(min_seconds, max_seconds))


def _clamp_duration(value: int) -> int:
    rounded = int(round(value / DURATION_STEP_SECONDS) * DURATION_STEP_SECONDS)
    return max(MIN_DURATION_SECONDS, min(MAX_DURATION_SECONDS, rounded))
