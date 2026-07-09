"""SQLite-backed topic queue for pipeline channels."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from lib.channel import default_db_path
from lib.topics import VALID_STATUSES, GENERATED_VIDEO_STATUSES, utc_now_iso

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _row_to_topic(row: sqlite3.Row) -> dict[str, Any]:
    music_profiles = json.loads(row["music_profiles"])
    return {
        "uid": row["uid"],
        "id": row["topic_id"],
        "category": row["category"],
        "topic": row["topic"],
        "topic_hash": row["topic_hash"],
        "music_profiles": music_profiles,
        "status": row["status"],
        "generated_at": row["generated_at"],
        "task_id": row["task_id"],
        "video_path": row["video_path"],
        "approved": bool(row["approved"]),
    }


class TopicStore:
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
            columns = self._topic_columns(conn)
            if columns and not {"uid", "topic_id"}.issubset(columns):
                self._migrate_legacy_topics_table(conn, sql)
            conn.executescript(sql)

    def _topic_columns(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("PRAGMA table_info(topics)").fetchall()
        return {str(row["name"]) for row in rows}

    def _migrate_legacy_topics_table(
        self, conn: sqlite3.Connection, schema_sql: str
    ) -> None:
        rows = conn.execute(
            """
            SELECT
              id,
              channel_slug,
              category,
              topic,
              topic_hash,
              music_profiles,
              status,
              generated_at,
              task_id,
              video_path,
              approved,
              created_at,
              updated_at
            FROM topics
            ORDER BY channel_slug, id
            """
        ).fetchall()
        conn.execute("ALTER TABLE topics RENAME TO topics_legacy")
        conn.executescript(schema_sql)
        for row in rows:
            conn.execute(
                """
                INSERT INTO topics (
                  uid, channel_slug, topic_id, category, topic, topic_hash,
                  music_profiles, status, generated_at, task_id, video_path,
                  approved, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    row["channel_slug"],
                    row["id"],
                    row["category"],
                    row["topic"],
                    row["topic_hash"],
                    row["music_profiles"],
                    row["status"],
                    row["generated_at"],
                    row["task_id"],
                    row["video_path"],
                    row["approved"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        conn.execute("DROP TABLE topics_legacy")

    def list_topics(self, channel_slug: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM topics
                WHERE channel_slug = ?
                ORDER BY topic_id
                """,
                (channel_slug,),
            ).fetchall()
        return [_row_to_topic(row) for row in rows]

    def find_by_id(self, channel_slug: str, topic_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM topics
                WHERE channel_slug = ? AND topic_id = ?
                """,
                (channel_slug, topic_id),
            ).fetchone()
        return _row_to_topic(row) if row else None

    def get_next_pending(self, channel_slug: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM topics
                WHERE channel_slug = ? AND status = 'pending'
                ORDER BY topic_id
                LIMIT 1
                """,
                (channel_slug,),
            ).fetchone()
        return _row_to_topic(row) if row else None

    def count_by_status(self, channel_slug: str) -> dict[str, int]:
        counts = {status: 0 for status in sorted(VALID_STATUSES)}
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM topics
                WHERE channel_slug = ?
                GROUP BY status
                """,
                (channel_slug,),
            ).fetchall()
        for row in rows:
            status = row["status"]
            if status in counts:
                counts[status] = row["cnt"]
            else:
                counts[status] = row["cnt"]
        return counts

    def count_generated_today(self, channel_slug: str) -> int:
        placeholders = ", ".join("?" for _ in GENERATED_VIDEO_STATUSES)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM topics
                WHERE channel_slug = ?
                  AND status IN ({placeholders})
                  AND generated_at IS NOT NULL
                  AND generated_at != ''
                  AND date(generated_at) = date('now')
                """,
                (channel_slug, *sorted(GENERATED_VIDEO_STATUSES)),
            ).fetchone()
        return int(row["cnt"])

    def next_id(self, channel_slug: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(topic_id), 0) + 1 AS next_id
                FROM topics
                WHERE channel_slug = ?
                """,
                (channel_slug,),
            ).fetchone()
        return int(row["next_id"])

    def insert_topics(
        self,
        channel_slug: str,
        records: list[dict[str, Any]],
        *,
        replace: bool = False,
    ) -> int:
        if not records:
            return 0
        now = utc_now_iso()
        inserted = 0
        with self._connect() as conn:
            for record in records:
                uid = str(record.get("uid") or uuid4())
                topic_id = int(record.get("topic_id") or record["id"])
                music_profiles = record.get("music_profiles", [])
                if replace:
                    conn.execute(
                        """
                        INSERT INTO topics (
                          uid, channel_slug, topic_id, category, topic, topic_hash,
                          music_profiles, status, generated_at, task_id,
                          video_path, approved, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(channel_slug, topic_id) DO UPDATE SET
                          category = excluded.category,
                          topic = excluded.topic,
                          topic_hash = excluded.topic_hash,
                          music_profiles = excluded.music_profiles,
                          status = excluded.status,
                          generated_at = excluded.generated_at,
                          task_id = excluded.task_id,
                          video_path = excluded.video_path,
                          approved = excluded.approved,
                          created_at = excluded.created_at,
                          updated_at = excluded.updated_at
                        """,
                        (
                            uid,
                            channel_slug,
                            topic_id,
                            record["category"],
                            record["topic"],
                            record["topic_hash"],
                            json.dumps(music_profiles, ensure_ascii=False),
                            record.get("status", "pending"),
                            record.get("generated_at"),
                            record.get("task_id"),
                            record.get("video_path"),
                            1 if record.get("approved") else 0,
                            record.get("created_at", now),
                            record.get("updated_at", now),
                        ),
                    )
                    inserted += 1
                else:
                    try:
                        conn.execute(
                            """
                            INSERT INTO topics (
                              uid, channel_slug, topic_id, category, topic, topic_hash,
                              music_profiles, status, generated_at, task_id,
                              video_path, approved, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                uid,
                                channel_slug,
                                topic_id,
                                record["category"],
                                record["topic"],
                                record["topic_hash"],
                                json.dumps(music_profiles, ensure_ascii=False),
                                record.get("status", "pending"),
                                record.get("generated_at"),
                                record.get("task_id"),
                                record.get("video_path"),
                                1 if record.get("approved") else 0,
                                record.get("created_at", now),
                                record.get("updated_at", now),
                            ),
                        )
                        inserted += 1
                    except sqlite3.IntegrityError:
                        continue
            conn.commit()
        return inserted

    def update_topic(self, channel_slug: str, topic: dict[str, Any]) -> None:
        topic_uid = topic.get("uid")
        topic_id = topic.get("id")
        if topic_uid is None and topic_id is None:
            raise ValueError("topic must have a uid or id")

        now = utc_now_iso()
        music_profiles = topic.get("music_profiles", [])
        with self._connect() as conn:
            params = (
                topic["category"],
                topic["topic"],
                topic["topic_hash"],
                json.dumps(music_profiles, ensure_ascii=False),
                topic.get("status", "pending"),
                topic.get("generated_at"),
                topic.get("task_id"),
                topic.get("video_path"),
                1 if topic.get("approved") else 0,
                now,
            )
            if topic_uid is not None:
                conn.execute(
                    """
                    UPDATE topics SET
                      category = ?,
                      topic = ?,
                      topic_hash = ?,
                      music_profiles = ?,
                      status = ?,
                      generated_at = ?,
                      task_id = ?,
                      video_path = ?,
                      approved = ?,
                      updated_at = ?
                    WHERE uid = ?
                    """,
                    params + (topic_uid,),
                )
            else:
                conn.execute(
                    """
                    UPDATE topics SET
                      category = ?,
                      topic = ?,
                      topic_hash = ?,
                      music_profiles = ?,
                      status = ?,
                      generated_at = ?,
                      task_id = ?,
                      video_path = ?,
                      approved = ?,
                      updated_at = ?
                    WHERE channel_slug = ? AND topic_id = ?
                    """,
                    params + (channel_slug, topic_id),
                )
            conn.commit()

    def has_topics(self, channel_slug: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM topics WHERE channel_slug = ? LIMIT 1",
                (channel_slug,),
            ).fetchone()
        return row is not None

    def clear_channel(self, channel_slug: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM topics WHERE channel_slug = ?",
                (channel_slug,),
            )
            conn.commit()
            return cursor.rowcount

    def existing_topic_texts(self, channel_slug: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT topic FROM topics
                WHERE channel_slug = ?
                ORDER BY topic_id
                """,
                (channel_slug,),
            ).fetchall()
        return [row["topic"] for row in rows]

    def import_from_json_file(
        self,
        channel_slug: str,
        json_path: Path,
        *,
        replace: bool = True,
    ) -> int:
        with open(json_path, encoding="utf-8") as f:
            items = json.load(f)
        if not isinstance(items, list):
            raise ValueError(f"topics file must be a JSON array: {json_path}")

        now = utc_now_iso()
        records = []
        for item in items:
            records.append(
                {
                    "uid": item.get("uid"),
                    "id": item["id"],
                    "category": item["category"],
                    "topic": item["topic"],
                    "topic_hash": item["topic_hash"],
                    "music_profiles": item.get("music_profiles", []),
                    "status": item.get("status", "pending"),
                    "generated_at": item.get("generated_at"),
                    "task_id": item.get("task_id"),
                    "video_path": item.get("video_path"),
                    "approved": item.get("approved", False),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        return self.insert_topics(channel_slug, records, replace=replace)
