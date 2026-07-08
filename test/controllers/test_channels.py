import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from lib import channel as channel_lib  # noqa: E402
from lib import topic_store as topic_store_lib  # noqa: E402

from app.asgi import app  # noqa: E402


class TestChannelsEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        self.channels_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.channels_tmp.cleanup)
        channels_root = Path(self.channels_tmp.name) / "channels"
        self.slug = "testchan"
        base = channels_root / self.slug
        base.mkdir(parents=True)
        (base / "channel.json").write_text(
            json.dumps(
                {
                    "slug": self.slug,
                    "name": "Test Channel",
                    "niche": "test niche",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (base / "script_prompt.md").write_text("Explique.\n", encoding="utf-8")
        self.channels_patcher = patch.object(channel_lib, "CHANNELS_DIR", channels_root)
        self.channels_patcher.start()
        self.addCleanup(self.channels_patcher.stop)

        self.db_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.db_tmp.cleanup)
        db_path = Path(self.db_tmp.name) / "pipeline.db"
        self.db_patcher = patch.object(topic_store_lib, "default_db_path", return_value=db_path)
        self.db_patcher.start()
        self.addCleanup(self.db_patcher.stop)

        self.workspace_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace_tmp.cleanup)
        self.workspace_patcher = patch(
            "app.services.workspace_store._workspace_dir",
            return_value=Path(self.workspace_tmp.name),
        )
        self.workspace_patcher.start()
        self.addCleanup(self.workspace_patcher.stop)

    def _seed_topic(self):
        store = topic_store_lib.TopicStore()
        store.insert_topics(
            self.slug,
            [
                {
                    "id": 1,
                    "category": "history",
                    "topic": "Templo em Kyoto",
                    "topic_hash": "abc123",
                    "status": "pending",
                }
            ],
        )
        return store.list_topics(self.slug)[0]

    def test_list_channels(self):
        response = self.client.get("/api/v1/channels")
        self.assertEqual(response.status_code, 200)
        slugs = [c["slug"] for c in response.json()["data"]["channels"]]
        self.assertIn(self.slug, slugs)

    def test_get_channel_detail(self):
        response = self.client.get(f"/api/v1/channels/{self.slug}")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["slug"], self.slug)
        self.assertEqual(data["runtime"]["video_subject"], "test niche")

    def test_get_channel_detail_unknown_404s(self):
        response = self.client.get("/api/v1/channels/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_list_topics_empty(self):
        response = self.client.get(f"/api/v1/channels/{self.slug}/topics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["topics"], [])

    def test_list_topics_returns_seeded_topic(self):
        self._seed_topic()
        response = self.client.get(f"/api/v1/channels/{self.slug}/topics")
        data = response.json()["data"]
        self.assertEqual(len(data["topics"]), 1)
        self.assertEqual(data["counts"]["pending"], 1)

    def test_load_topic_into_workspace(self):
        topic = self._seed_topic()
        response = self.client.post(
            f"/api/v1/channels/{self.slug}/topics/{topic['uid']}/load-into-workspace"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["workspace"]["script"]["video_subject"], "Templo em Kyoto")

    def test_load_topic_into_workspace_unknown_uid_404s(self):
        response = self.client.post(
            f"/api/v1/channels/{self.slug}/topics/does-not-exist/load-into-workspace"
        )
        self.assertEqual(response.status_code, 404)

    def test_update_topic_status(self):
        topic = self._seed_topic()
        response = self.client.patch(
            f"/api/v1/channels/{self.slug}/topics/{topic['uid']}",
            json={"status": "approved", "approved": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "approved")

    def test_update_topic_status_rejects_invalid_status(self):
        topic = self._seed_topic()
        response = self.client.patch(
            f"/api/v1/channels/{self.slug}/topics/{topic['uid']}",
            json={"status": "not-a-real-status"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
