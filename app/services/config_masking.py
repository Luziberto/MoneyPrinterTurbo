"""Secret masking for the cockpit's Config endpoint.

config.toml holds live provider API keys/secrets. GET /api/v1/config must
never return them in the clear; PUT must treat an unchanged masked value
(sent back by a client that only edited a sibling field) as "no change"
rather than overwriting the real secret with the mask string.
"""

from __future__ import annotations

from typing import Any

_SECRET_MARKERS = ("key", "secret", "password", "token")
MASK_INFIX = "***"


def is_secret_field(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def mask_value(value: Any) -> str:
    text = str(value)
    if not text:
        return text
    if len(text) <= 8:
        return MASK_INFIX
    return f"{text[:4]}{MASK_INFIX}{text[-4:]}"


def mask_section(section: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in section.items():
        if is_secret_field(key) and value:
            masked[key] = mask_value(value)
        else:
            masked[key] = value
    return masked


def apply_section_patch(section: dict[str, Any], patch: dict[str, Any]) -> None:
    """Merge `patch` into the live `section` dict, in place.

    Skips any secret field whose incoming value still contains the mask
    infix (the client echoing back what GET returned, unedited).
    """
    for key, value in patch.items():
        if is_secret_field(key) and isinstance(value, str) and MASK_INFIX in value:
            continue
        section[key] = value
