import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from lib.topic_store import TopicStore


def _topic_record(topic_id: int, topic: str, topic_hash: str) -> dict:
    return {
        "id": topic_id,
        "category": "culture",
        "topic": topic,
        "topic_hash": topic_hash,
        "music_profiles": ["lofi"],
        "status": "pending",
        "generated_at": None,
        "task_id": None,
        "video_path": None,
        "approved": False,
    }


class TopicStoreTestCase(unittest.TestCase):
    def test_same_topic_id_can_exist_in_multiple_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pipeline.db"
            store = TopicStore(db_path)

            inserted_a = store.insert_topics(
                "japao",
                [_topic_record(1, "Tema A", "hash-a")],
            )
            inserted_b = store.insert_topics(
                "tech",
                [_topic_record(1, "Tema B", "hash-b")],
            )

            self.assertEqual(inserted_a, 1)
            self.assertEqual(inserted_b, 1)
            self.assertEqual(store.find_by_id("japao", 1)["id"], 1)
            self.assertEqual(store.find_by_id("tech", 1)["id"], 1)
            self.assertNotEqual(
                store.find_by_id("japao", 1)["uid"],
                store.find_by_id("tech", 1)["uid"],
            )

    def test_migrates_legacy_schema_to_uid_and_topic_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pipeline.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE topics (
                  id INTEGER PRIMARY KEY,
                  channel_slug TEXT NOT NULL,
                  category TEXT NOT NULL,
                  topic TEXT NOT NULL,
                  topic_hash TEXT NOT NULL,
                  music_profiles TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  generated_at TEXT,
                  task_id TEXT,
                  video_path TEXT,
                  approved INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO topics (
                  id, channel_slug, category, topic, topic_hash, music_profiles,
                  status, generated_at, task_id, video_path, approved, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "japao",
                    "culture",
                    "Tema legado",
                    "legacy-hash",
                    '["lofi"]',
                    "pending",
                    None,
                    None,
                    None,
                    0,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            conn.commit()
            conn.close()

            store = TopicStore(db_path)
            migrated = store.find_by_id("japao", 1)

            self.assertIsNotNone(migrated)
            self.assertTrue(migrated["uid"])
            self.assertEqual(migrated["id"], 1)
            self.assertEqual(store.next_id("japao"), 2)

            with sqlite3.connect(db_path) as verify_conn:
                columns = {
                    row[1]
                    for row in verify_conn.execute("PRAGMA table_info(topics)").fetchall()
                }
            self.assertIn("uid", columns)
            self.assertIn("topic_id", columns)
            self.assertNotIn("id", columns)

    def test_count_generated_today_ignores_pending_and_other_days(self) -> None:
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pipeline.db"
            store = TopicStore(db_path)

            store.insert_topics(
                "japao",
                [
                    {
                        **_topic_record(1, "Hoje gerado", "hash-1"),
                        "status": "generated",
                        "generated_at": today,
                    },
                    {
                        **_topic_record(2, "Hoje aprovado", "hash-2"),
                        "status": "approved",
                        "generated_at": today,
                    },
                    {
                        **_topic_record(3, "Ontem", "hash-3"),
                        "status": "generated",
                        "generated_at": yesterday,
                    },
                    {
                        **_topic_record(4, "Pendente", "hash-4"),
                        "status": "pending",
                        "generated_at": today,
                    },
                ],
            )

            self.assertEqual(store.count_generated_today("japao"), 2)
            self.assertEqual(store.count_generated_today("tech"), 0)


if __name__ == "__main__":
    unittest.main()
