"""Mode registry for editorial defaults (VisualAI spec 015, trimmed for MPT)."""

from __future__ import annotations

from typing import Any, Final

from . import faceless

_REGISTRY: Final[dict[str, Any]] = {
    "faceless": faceless,
}


def supported_modes() -> list[str]:
    return list(_REGISTRY.keys())


def pick_mode(name: str):
    if name not in _REGISTRY:
        raise KeyError(
            f"unsupported_mode: {name!r}. Supported: {supported_modes()}"
        )
    return _REGISTRY[name]


def apply_mode_defaults(config: dict[str, Any]) -> dict[str, Any]:
    mode_name = str(config.get("mode") or "faceless").strip() or "faceless"
    if mode_name not in _REGISTRY:
        return config
    defaults = pick_mode(mode_name).MODE_DEFAULTS
    merged = dict(config)
    for key, value in defaults.items():
        if key not in merged or merged.get(key) in (None, "", []):
            merged[key] = value
    merged["mode"] = mode_name
    return merged
