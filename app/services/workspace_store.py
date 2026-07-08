"""Atomic per-channel JSON persistence for the cockpit Workspace.

Replaces Streamlit's st.session_state as the source of truth for an
in-progress video draft. One JSON file per channel slug under
storage/mpt_runtime/workspace/, written atomically (temp file + os.replace),
mirroring the pattern already used by app/services/runtime_limits.py for the
generation lock file.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schema import Workspace, WorkspacePatch
from app.utils import utils

_UNASSIGNED_SLUG = "_unassigned"
_SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_locks_guard = threading.Lock()
_slug_locks: dict[str, threading.Lock] = {}


def _lock_for(slug: str) -> threading.Lock:
    with _locks_guard:
        lock = _slug_locks.get(slug)
        if lock is None:
            lock = threading.Lock()
            _slug_locks[slug] = lock
        return lock


def _normalize_slug(channel_slug: str | None) -> str:
    slug = str(channel_slug or "").strip()
    if not slug:
        return _UNASSIGNED_SLUG
    if not _SAFE_SLUG_RE.match(slug):
        raise ValueError(f"invalid channel_slug: {channel_slug!r}")
    return slug


def _workspace_dir() -> Path:
    return Path(utils.storage_dir("mpt_runtime/workspace", create=True))


def _workspace_path(slug: str) -> Path:
    return _workspace_dir() / f"{slug}.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp-{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_workspace(channel_slug: str | None, *, seed: dict[str, Any] | None = None) -> Workspace:
    """Load the workspace for a channel, lazily creating it from `seed` if absent."""
    slug = _normalize_slug(channel_slug)
    path = _workspace_path(slug)
    with _lock_for(slug):
        if not path.is_file():
            workspace = Workspace(channel_slug=channel_slug, **(seed or {}))
            workspace.updated_at = _now_iso()
            _atomic_write_json(path, workspace.model_dump(mode="json"))
            return workspace

        raw = json.loads(path.read_text(encoding="utf-8"))
        return Workspace(**raw)


def save_workspace(workspace: Workspace) -> Workspace:
    slug = _normalize_slug(workspace.channel_slug)
    path = _workspace_path(slug)
    workspace.updated_at = _now_iso()
    with _lock_for(slug):
        _atomic_write_json(path, workspace.model_dump(mode="json"))
    return workspace


def patch_workspace(channel_slug: str | None, patch: WorkspacePatch) -> Workspace:
    slug = _normalize_slug(channel_slug)
    path = _workspace_path(slug)
    patch_data = patch.model_dump(exclude_none=True)

    with _lock_for(slug):
        if path.is_file():
            current = json.loads(path.read_text(encoding="utf-8"))
        else:
            current = Workspace(channel_slug=channel_slug).model_dump(mode="json")

        merged = _deep_merge(current, patch_data)
        merged["channel_slug"] = channel_slug
        workspace = Workspace(**merged)
        workspace.updated_at = _now_iso()
        _atomic_write_json(path, workspace.model_dump(mode="json"))
        return workspace


def reset_workspace(channel_slug: str | None, seed: dict[str, Any]) -> Workspace:
    """Overwrite the workspace with fresh channel defaults, clearing overrides/preview."""
    slug = _normalize_slug(channel_slug)
    path = _workspace_path(slug)
    workspace = Workspace(channel_slug=channel_slug, **seed)
    workspace.overrides = []
    workspace.preview.ready = False
    workspace.updated_at = _now_iso()
    with _lock_for(slug):
        _atomic_write_json(path, workspace.model_dump(mode="json"))
    return workspace
