import tempfile
import unittest
from pathlib import Path

from app.services.video_library_store import VideoLibraryStore


class VideoLibraryStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.store = VideoLibraryStore(Path(self.tmpdir.name) / "videos.db")

    def test_create_and_get_video_round_trips_all_fields(self):
        video = self.store.create_video(
            id="task-1",
            channel_slug="japao",
            title="Kyoto em 1 minuto",
            subject="Kyoto",
            keywords=["kyoto", "japao"],
            tags=["viagem"],
            pipeline_version="MoneyPrinterTurbo 1.3.0",
            source="cockpit",
        )
        self.assertEqual(video["id"], "task-1")
        self.assertEqual(video["status"], "rendering")
        self.assertEqual(video["keywords"], ["kyoto", "japao"])
        self.assertEqual(video["tags"], ["viagem"])
        self.assertIsNone(video["project_id"])
        self.assertEqual(video["source"], "cockpit")

        fetched = self.store.get_video("task-1")
        self.assertEqual(fetched, video)

    def test_get_video_returns_none_for_missing_id(self):
        self.assertIsNone(self.store.get_video("does-not-exist"))

    def test_update_video_persists_every_field_passed(self):
        # Regression guard for the TopicStore.update_topic() bug this design
        # deliberately avoids: every field passed to update_video() must
        # actually land in the row, not just the ones a hand-maintained
        # column list happened to remember.
        self.store.create_video(id="task-1", channel_slug="japao")
        updated = self.store.update_video(
            "task-1",
            status="ready",
            thumbnail_path="/tasks/task-1/final-1-thumbnail.jpg",
            video_path="/tasks/task-1/final-1.mp4",
            duration_seconds=42.5,
            file_size_bytes=123456,
            keywords=["a", "b"],
        )
        self.assertEqual(updated["status"], "ready")
        self.assertEqual(updated["thumbnail_path"], "/tasks/task-1/final-1-thumbnail.jpg")
        self.assertEqual(updated["video_path"], "/tasks/task-1/final-1.mp4")
        self.assertEqual(updated["duration_seconds"], 42.5)
        self.assertEqual(updated["file_size_bytes"], 123456)
        self.assertEqual(updated["keywords"], ["a", "b"])

    def test_list_videos_filters_by_status_and_channel(self):
        self.store.create_video(id="t1", channel_slug="japao", status="ready")
        self.store.create_video(id="t2", channel_slug="japao", status="failed")
        self.store.create_video(id="t3", channel_slug="other", status="ready")

        ready_japao, total = self.store.list_videos(status="ready", channel_slug="japao")
        self.assertEqual(total, 1)
        self.assertEqual([v["id"] for v in ready_japao], ["t1"])

    def test_list_videos_paginates(self):
        for i in range(5):
            self.store.create_video(id=f"t{i}", channel_slug="japao")
        page1, total = self.store.list_videos(page=1, page_size=2)
        page2, _ = self.store.list_videos(page=2, page_size=2)
        self.assertEqual(total, 5)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual([v["id"] for v in page1], [v["id"] for v in page2])

    def test_delete_video_removes_row_and_related_publications_and_events(self):
        self.store.create_video(id="t1", channel_slug="japao")
        pub = self.store.create_publication(video_id="t1", platform="tiktok", provider="zernio")
        self.store.add_event(video_id="t1", type="status_changed", actor="system", data={})

        self.assertTrue(self.store.delete_video("t1"))
        self.assertIsNone(self.store.get_video("t1"))
        self.assertIsNone(self.store.get_publication(pub["id"]))
        self.assertEqual(self.store.list_events("t1"), [])

    def test_delete_video_returns_false_for_missing_id(self):
        self.assertFalse(self.store.delete_video("nope"))

    def test_count_by_status_covers_all_seven_statuses(self):
        self.store.create_video(id="t1", channel_slug="japao", status="ready")
        self.store.create_video(id="t2", channel_slug="japao", status="ready")
        self.store.create_video(id="t3", channel_slug="japao", status="failed")
        counts = self.store.count_by_status()
        self.assertEqual(counts["ready"], 2)
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["draft"], 0)
        self.assertEqual(
            set(counts.keys()),
            {"draft", "rendering", "ready", "scheduled", "published", "archived", "failed"},
        )

    def test_publication_round_trip(self):
        self.store.create_video(id="t1", channel_slug="japao")
        pub = self.store.create_publication(
            video_id="t1", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2026-07-10T00:00:00+00:00",
        )
        self.assertEqual(pub["status"], "scheduled")

        updated = self.store.update_publication(
            pub["id"], status="published", url="https://tiktok.com/x", result={"ok": True}
        )
        self.assertEqual(updated["status"], "published")
        self.assertEqual(updated["url"], "https://tiktok.com/x")
        self.assertEqual(updated["result"], {"ok": True})

        listed = self.store.list_publications("t1")
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], pub["id"])

    def test_list_due_publications_only_returns_scheduled_in_the_past(self):
        self.store.create_video(id="t1", channel_slug="japao")
        due = self.store.create_publication(
            video_id="t1", platform="tiktok", provider="zernio", status="scheduled",
            scheduled_at="2020-01-01T00:00:00+00:00",
        )
        self.store.create_publication(
            video_id="t1", platform="youtube", provider="zernio", status="scheduled",
            scheduled_at="2099-01-01T00:00:00+00:00",
        )
        self.store.create_publication(
            video_id="t1", platform="instagram", provider="zernio", status="published",
        )

        due_now = self.store.list_due_publications(now_iso="2026-07-08T00:00:00+00:00")
        self.assertEqual([p["id"] for p in due_now], [due["id"]])

    def test_events_are_listed_newest_first(self):
        self.store.create_video(id="t1", channel_slug="japao")
        self.store.add_event(video_id="t1", type="status_changed", actor="system", data={"to": "rendering"})
        self.store.add_event(video_id="t1", type="status_changed", actor="system", data={"to": "ready"})
        events = self.store.list_events("t1")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["data"]["to"], "ready")

    def test_avg_stage_seconds_returns_none_when_no_matching_events(self):
        self.store.create_video(id="t1", channel_slug="japao")
        self.assertIsNone(self.store.avg_stage_seconds("render"))

    def test_avg_stage_seconds_averages_matching_stage_only(self):
        self.store.create_video(id="t1", channel_slug="japao")
        self.store.add_event(
            video_id="t1", type="stage_completed", actor="system",
            data={"stage": "render", "elapsed_seconds": 10.0},
        )
        self.store.add_event(
            video_id="t1", type="stage_completed", actor="system",
            data={"stage": "render", "elapsed_seconds": 20.0},
        )
        self.store.add_event(
            video_id="t1", type="stage_completed", actor="system",
            data={"stage": "tts", "elapsed_seconds": 999.0},
        )
        self.assertEqual(self.store.avg_stage_seconds("render"), 15.0)


if __name__ == "__main__":
    unittest.main()
