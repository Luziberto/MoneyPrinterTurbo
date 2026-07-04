"""Detect and persist silent BGM mixing failures (VisualAI spec 011)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.utils import utils

_SIDECAR_NAME = "bgm_failed.json"
_TASK_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def extract_task_id_from_path(path: str) -> str | None:
    match = _TASK_ID_PATTERN.search(path or "")
    return match.group(0) if match else None


def sidecar_path(task_id: str) -> Path:
    return Path(utils.task_dir(task_id)) / _SIDECAR_NAME


def record_bgm_failure(
    *,
    output_file: str,
    reason: str,
    params: Any,
) -> None:
    bgm_type = (params.bgm_type or "").strip().lower()
    if not bgm_type or bgm_type in {"none", "off", "disable", "disabled"}:
        return

    task_id = extract_task_id_from_path(output_file)
    if not task_id:
        logger.warning(f"bgm audit: could not resolve task id from {output_file}")
        return

    payload: dict[str, Any] = {
        "reason": reason,
        "bgm_type": params.bgm_type,
        "bgm_file": params.bgm_file or "",
        "bgm_profile": getattr(params, "bgm_profile", "") or "",
        "timestamp": _utc_now_iso(),
    }

    path = sidecar_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        previous = existing.get("previous_failures") or []
        previous.append(
            {
                "reason": existing.get("reason"),
                "timestamp": existing.get("timestamp"),
            }
        )
        payload["previous_failures"] = previous[-5:]

    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning(f"bgm audit: failed to write sidecar for {task_id}: {exc}")


def read_bgm_failure(task_id: str) -> dict[str, Any] | None:
    path = sidecar_path(task_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
