"""SQLite-backed Video Library store.

Independent of pipeline/lib/topic_store.py's pipeline.db -- a video can exist
without ever touching a pipeline topic. Follows the same pattern (schema.sql
+ a *Store class wrapping sqlite3.connect() + sqlite3.Row) but deliberately
avoids TopicStore.update_topic()'s bug, where a hand-maintained UPDATE ... SET
column list silently drifted out of sync with what callers actually set
(published_at/publish_platforms/publish_results were set on the in-memory
dict but never written to SQLite). Every write here goes through
_update_row(), whose SET clause is built from the literal set of fields
passed in -- there is no separate column list to fall out of sync.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.utils import utils

SCHEMA_PATH = Path(__file__).resolve().parent / "video_library_schema.sql"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db_path() -> Path:
    return Path(utils.storage_dir("mpt_runtime", create=True)) / "videos.db"


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _row_to_video(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "channel_slug": row["channel_slug"],
        "title": row["title"],
        "subject": row["subject"],
        "keywords": _json_load(row["keywords"], []),
        "thumbnail_path": row["thumbnail_path"],
        "video_path": row["video_path"],
        "duration_seconds": row["duration_seconds"],
        "file_size_bytes": row["file_size_bytes"],
        "tags": _json_load(row["tags"], []),
        "caption": row["caption"],
        "status": row["status"],
        "error": row["error"],
        "pipeline_version": row["pipeline_version"],
        "source": row["source"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_publication(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "video_id": row["video_id"],
        "platform": row["platform"],
        "provider": row["provider"],
        "status": row["status"],
        "scheduled_at": row["scheduled_at"],
        "published_at": row["published_at"],
        "url": row["url"],
        "error": row["error"],
        "result": _json_load(row["result"], None),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "video_id": row["video_id"],
        "type": row["type"],
        "actor": row["actor"],
        "created_at": row["created_at"],
        "data": _json_load(row["data"], {}),
    }


class VideoLibraryStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else default_db_path()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)

    def _update_row(self, table: str, row_id: str, id_column: str = "id", **fields: Any) -> None:
        """Generic guarded UPDATE. The SET clause is built from `fields`
        itself, so a field passed here is always persisted -- there is no
        separate hand-maintained column list that can silently drop one.
        """
        if not fields:
            return
        payload = dict(fields)
        if "updated_at" not in payload:
            payload["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{key} = ?" for key in payload)
        values = list(payload.values()) + [row_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?", values)
            conn.commit()

    # ------------------------------------------------------------------
    # videos
    # ------------------------------------------------------------------

    def create_video(
        self,
        *,
        id: str,
        channel_slug: str,
        title: str = "",
        subject: str = "",
        keywords: list | None = None,
        tags: list | None = None,
        status: str = "rendering",
        pipeline_version: str | None = None,
        source: str = "api",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                  id, project_id, channel_slug, title, subject, keywords,
                  tags, status, pipeline_version, source, created_at, updated_at
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id,
                    channel_slug,
                    title,
                    subject,
                    _json_dump(keywords),
                    _json_dump(tags),
                    status,
                    pipeline_version,
                    source,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_video(id)

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        return _row_to_video(row) if row else None

    def list_videos(
        self,
        *,
        status: str | None = None,
        channel_slug: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if channel_slug:
            clauses.append("channel_slug = ?")
            params.append(channel_slug)
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if date_from:
            clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("created_at <= ?")
            params.append(date_to)
        if q:
            clauses.append("(title LIKE ? OR subject LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = max(0, (page - 1) * page_size)

        with self._connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM videos {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM videos {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
        return [_row_to_video(row) for row in rows], int(total)

    def update_video(self, video_id: str, **fields: Any) -> dict[str, Any] | None:
        if "keywords" in fields:
            fields["keywords"] = _json_dump(fields["keywords"])
        if "tags" in fields:
            fields["tags"] = _json_dump(fields["tags"])
        self._update_row("videos", video_id, **fields)
        return self.get_video(video_id)

    def delete_video(self, video_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM video_events WHERE video_id = ?", (video_id,))
            conn.execute("DELETE FROM video_publications WHERE video_id = ?", (video_id,))
            cursor = conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count_by_status(self, channel_slug: str | None = None) -> dict[str, int]:
        statuses = ("draft", "rendering", "ready", "scheduled", "published", "archived", "failed")
        counts = {status: 0 for status in statuses}
        where = "WHERE channel_slug = ?" if channel_slug else ""
        params = [channel_slug] if channel_slug else []
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS cnt FROM videos {where} GROUP BY status", params
            ).fetchall()
        for row in rows:
            counts[row["status"]] = row["cnt"]
        return counts

    def count_created_since(self, since_iso: str, channel_slug: str | None = None) -> int:
        clauses = ["created_at >= ?"]
        params: list[Any] = [since_iso]
        if channel_slug:
            clauses.append("channel_slug = ?")
            params.append(channel_slug)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM videos WHERE {' AND '.join(clauses)}", params
            ).fetchone()
        return int(row["cnt"])

    def count_reached_ready(self, channel_slug: str | None = None) -> int:
        statuses = ("ready", "scheduled", "published", "archived")
        placeholders = ", ".join("?" for _ in statuses)
        clauses = [f"status IN ({placeholders})"]
        params: list[Any] = list(statuses)
        if channel_slug:
            clauses.append("channel_slug = ?")
            params.append(channel_slug)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM videos WHERE {' AND '.join(clauses)}", params
            ).fetchone()
        return int(row["cnt"])

    def recent_failed(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM videos WHERE status = 'failed' ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_video(row) for row in rows]

    # ------------------------------------------------------------------
    # video_publications
    # ------------------------------------------------------------------

    def create_publication(
        self,
        *,
        video_id: str,
        platform: str,
        provider: str,
        status: str = "scheduled",
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        pub_id = str(uuid4())
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO video_publications (
                  id, video_id, platform, provider, status, scheduled_at,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pub_id, video_id, platform, provider, status, scheduled_at, now, now),
            )
            conn.commit()
        return self.get_publication(pub_id)

    def get_publication(self, pub_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM video_publications WHERE id = ?", (pub_id,)
            ).fetchone()
        return _row_to_publication(row) if row else None

    def list_publications(self, video_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM video_publications WHERE video_id = ? ORDER BY created_at DESC",
                (video_id,),
            ).fetchall()
        return [_row_to_publication(row) for row in rows]

    def update_publication(self, pub_id: str, **fields: Any) -> dict[str, Any] | None:
        if "result" in fields:
            fields["result"] = _json_dump(fields["result"])
        self._update_row("video_publications", pub_id, **fields)
        return self.get_publication(pub_id)

    def list_due_publications(self, now_iso: str | None = None) -> list[dict[str, Any]]:
        now_iso = now_iso or utc_now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM video_publications
                WHERE status = 'scheduled' AND scheduled_at IS NOT NULL AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                """,
                (now_iso,),
            ).fetchall()
        return [_row_to_publication(row) for row in rows]

    # ------------------------------------------------------------------
    # video_events
    # ------------------------------------------------------------------

    def add_event(
        self, *, video_id: str, type: str, actor: str, data: dict | None = None
    ) -> dict[str, Any]:
        event_id = str(uuid4())
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO video_events (id, video_id, type, actor, created_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, video_id, type, actor, now, json.dumps(data or {}, ensure_ascii=False)),
            )
            conn.commit()
        return {"id": event_id, "video_id": video_id, "type": type, "actor": actor, "created_at": now, "data": data or {}}

    def list_events(self, video_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM video_events WHERE video_id = ? ORDER BY created_at DESC",
                (video_id,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def avg_stage_seconds(self, stage: str, limit: int = 50) -> float | None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT data FROM video_events
                WHERE type = 'stage_completed'
                ORDER BY created_at DESC
                LIMIT 500
                """,
            ).fetchall()
        elapsed: list[float] = []
        for row in rows:
            payload = _json_load(row["data"], {})
            if payload.get("stage") == stage and "elapsed_seconds" in payload:
                elapsed.append(float(payload["elapsed_seconds"]))
                if len(elapsed) >= limit:
                    break
        if not elapsed:
            return None
        return sum(elapsed) / len(elapsed)
