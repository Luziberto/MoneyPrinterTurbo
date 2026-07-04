"""Runtime caps and single-flight generation lock for WebUI/batch safety."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


class GenerationAlreadyRunningError(RuntimeError):
    """Raised when another generation holds the runtime lock."""


_ROOT_DIR = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(float(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RuntimeLimits:
    low_memory_mode: bool
    max_threads: int
    max_remote_video_mb: int
    max_downloads_per_task: int
    generation_lock_ttl_seconds: int
    max_queued_tasks_hint: int

    @property
    def max_remote_video_bytes(self) -> int:
        return self.max_remote_video_mb * 1024 * 1024


def get_runtime_limits() -> RuntimeLimits:
    low_memory = _env_bool("MPT_LOW_MEMORY_MODE", False)
    return RuntimeLimits(
        low_memory_mode=low_memory,
        max_threads=_env_int("MPT_MAX_THREADS", 1 if low_memory else 4, 1),
        max_remote_video_mb=_env_int("MPT_MAX_REMOTE_VIDEO_MB", 48 if low_memory else 192, 1),
        max_downloads_per_task=_env_int("MPT_MAX_DOWNLOADS_PER_TASK", 4 if low_memory else 12, 1),
        generation_lock_ttl_seconds=_env_int(
            "MPT_GENERATION_LOCK_TTL_SECONDS", 600 if low_memory else 1800, 60
        ),
        max_queued_tasks_hint=_env_int("MPT_MAX_QUEUED_TASKS", 20, 1),
    )


def cap_thread_count(requested: int | None) -> int:
    limits = get_runtime_limits()
    value = int(requested or 1)
    return max(1, min(value, limits.max_threads))


def runtime_dir() -> Path:
    path = _ROOT_DIR / "storage" / "mpt_runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generation_lock_path() -> Path:
    return runtime_dir() / "generation.lock"


def _read_lock_data(lock: Path) -> dict[str, Any] | None:
    if not lock.is_file():
        return None
    try:
        return json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _remove_lock_if_matches(lock: Path, expected: dict[str, Any]) -> bool:
    current = _read_lock_data(lock)
    if not current:
        return False
    for key in ("task_id", "owner", "created_at_epoch"):
        if current.get(key) != expected.get(key):
            return False
    try:
        lock.unlink()
        return True
    except OSError:
        return False


def generation_lock_status() -> dict[str, Any] | None:
    lock = generation_lock_path()
    if not lock.is_file():
        return None

    data = _read_lock_data(lock)
    ttl = get_runtime_limits().generation_lock_ttl_seconds
    now = time.time()

    if data:
        created = float(data.get("created_at_epoch", 0) or 0)
        if created and now - created > ttl:
            _remove_lock_if_matches(lock, data)
            return None
        return data

    try:
        if now - lock.stat().st_mtime <= ttl:
            return {"status": "running", "task_id": "unknown"}
        lock.unlink(missing_ok=True)
    except OSError:
        return {"status": "running", "task_id": "unknown"}
    return None


def clear_stale_generation_lock(*, force: bool = False) -> bool:
    lock = generation_lock_path()
    if not lock.is_file():
        return False
    if force:
        try:
            lock.unlink()
            return True
        except OSError:
            return False

    status = generation_lock_status()
    if status is None and lock.is_file():
        try:
            lock.unlink()
            return True
        except OSError:
            return False
    return False


def _atomic_write_lock(lock: Path, metadata: dict[str, Any]) -> bool:
    fd: int | None = None
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            fd = None
            lock_file.write(json.dumps(metadata, ensure_ascii=False))
            lock_file.flush()
            os.fsync(lock_file.fileno())
        return True
    except FileExistsError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def single_flight_generation_lock(task_id: str) -> Iterator[None]:
    lock = generation_lock_path()
    owner = uuid4().hex
    metadata = {
        "task_id": task_id,
        "owner": owner,
        "created_at_epoch": time.time(),
        "status": "running",
    }
    acquired = _atomic_write_lock(lock, metadata)
    if not acquired:
        current = generation_lock_status()
        if current:
            raise GenerationAlreadyRunningError(current.get("task_id", "unknown"))
        acquired = _atomic_write_lock(lock, metadata)
        if not acquired:
            raise GenerationAlreadyRunningError("unknown")

    try:
        yield
    finally:
        current = _read_lock_data(lock)
        if current and current.get("owner") == owner:
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                pass
