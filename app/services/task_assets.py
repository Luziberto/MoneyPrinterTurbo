"""Filename-agnostic asset discovery for a render task's output directory.

Every other module that needs "the thumbnail path" or "the final video path"
goes through this, instead of hardcoding filenames inline -- this is the one
place on-disk naming conventions are known, so a future rename (e.g.
audio.mp3 -> audio.wav, or subtitles moving into a subfolder) is a one-file
change instead of an API-wide one.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from app.config import config
from app.utils import utils

# kind -> glob patterns tried in order, relative to the task directory.
_ASSET_PATTERNS: dict[str, tuple[str, ...]] = {
    "video": ("final-*.mp4",),
    "thumbnail": ("*thumbnail*.jpg", "*thumbnail*.jpeg", "*thumbnail*.png", "*thumbnail*.webp"),
    "audio": ("audio.*",),
    "subtitle": ("subtitle.*", "subtitles/*"),
    "script": ("script.json",),
}


@dataclass
class TaskAsset:
    kind: str
    name: str
    size_bytes: int
    url: str


def _task_file_url(task_id: str, filename: str) -> str:
    endpoint = str(config.app.get("endpoint", "") or "").rstrip("/")
    path = f"tasks/{task_id}/{filename}"
    return f"{endpoint}/{path}" if endpoint else f"/{path}"


def find(task_id: str, kind: str) -> Optional[TaskAsset]:
    """Return the first asset of `kind` that actually exists on disk, or None."""
    patterns = _ASSET_PATTERNS.get(kind)
    if not patterns:
        return None

    base_dir = utils.task_dir(task_id)
    for pattern in patterns:
        matches = sorted(glob.glob(os.path.join(base_dir, pattern)))
        for match in matches:
            if os.path.isfile(match):
                filename = os.path.relpath(match, base_dir).replace(os.sep, "/")
                return TaskAsset(
                    kind=kind,
                    name=filename,
                    size_bytes=os.path.getsize(match),
                    url=_task_file_url(task_id, filename),
                )
    return None


def list_assets(task_id: str) -> list[TaskAsset]:
    """Every produced asset for a task that currently exists on disk."""
    assets = []
    for kind in _ASSET_PATTERNS:
        asset = find(task_id, kind)
        if asset:
            assets.append(asset)
    return assets


def read_script_json(task_id: str) -> Optional[dict[str, Any]]:
    """The {script, search_terms, params} blob written by task.py::save_script_data().

    Used by the Video Library API for lazy script/keyword display and for
    re-render (params round-trip). Returns None if the task never reached
    the script-saving stage (e.g. it failed before terms/audio) or the file
    is unreadable.
    """
    script_path = os.path.join(utils.task_dir(task_id), "script.json")
    if not os.path.isfile(script_path):
        return None
    try:
        with open(script_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        logger.warning(f"failed to read script.json for {task_id}: {exc}")
        return None
