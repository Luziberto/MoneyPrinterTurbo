import tempfile
import unittest
from pathlib import Path

from app.services import video_library_transitions as transitions
from app.services.video_library_store import VideoLibraryStore


class VideoLibraryTransitionsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.store = VideoLibraryStore(Path(self.tmpdir.name) / "videos.db")
        self.store.create_video(id="t1", channel_slug="japao", status="rendering")

    def test_mark_ready_sets_status_and_writes_event(self):
        video = transitions.mark_ready(
            self.store, "t1",
            thumbnail_path="/tasks/t1/final-1-thumbnail.jpg",
            video_path="/tasks/t1/final-1.mp4",
            duration_seconds=30.0,
            file_size_bytes=1000,
            keywords=["a"],
        )
        self.assertEqual(video["status"], "ready")
        self.assertEqual(video["thumbnail_path"], "/tasks/t1/final-1-thumbnail.jpg")
        events = self.store.list_events("t1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "status_changed")
        self.assertEqual(events[0]["data"], {"from": "rendering", "to": "ready"})

    def test_mark_ready_raises_for_missing_video(self):
        with self.assertRaises(ValueError):
            transitions.mark_ready(self.store, "missing")

    def test_mark_failed_sets_status_and_error(self):
        video = transitions.mark_failed(self.store, "t1", error="ffmpeg exploded")
        self.assertEqual(video["status"], "failed")
        self.assertEqual(video["error"], "ffmpeg exploded")
        events = self.store.list_events("t1")
        self.assertEqual(events[0]["type"], "error")

    def test_mark_archived_requires_archivable_status(self):
        with self.assertRaises(ValueError):
            transitions.mark_archived(self.store, "t1")  # still 'rendering'

        transitions.mark_ready(self.store, "t1")
        video = transitions.mark_archived(self.store, "t1")
        self.assertEqual(video["status"], "archived")

    def test_mark_restored_requires_archived_status(self):
        with self.assertRaises(ValueError):
            transitions.mark_restored(self.store, "t1")  # still 'rendering'

    def test_mark_restored_resyncs_rollup_to_ready_when_no_publications(self):
        transitions.mark_ready(self.store, "t1")
        transitions.mark_archived(self.store, "t1")
        video = transitions.mark_restored(self.store, "t1")
        self.assertEqual(video["status"], "ready")

    def test_sync_rollup_status_ignores_non_rollup_eligible_videos(self):
        # 'rendering' is not in the rollup-eligible set -- must be a no-op.
        video = transitions.sync_rollup_status(self.store, "t1")
        self.assertEqual(video["status"], "rendering")

    def test_schedule_publications_creates_rows_and_rolls_up_to_scheduled(self):
        transitions.mark_ready(self.store, "t1")
        created = transitions.schedule_publications(
            self.store, "t1",
            platforms=["tiktok", "youtube"],
            provider="zernio",
            scheduled_at="2026-08-01T00:00:00+00:00",
        )
        self.assertEqual(len(created), 2)
        video = self.store.get_video("t1")
        self.assertEqual(video["status"], "scheduled")

    def test_mark_publication_published_rolls_video_up_to_published(self):
        transitions.mark_ready(self.store, "t1")
        pub = self.store.create_publication(
            video_id="t1", platform="tiktok", provider="zernio", status="publishing",
        )
        transitions.mark_publication_published(self.store, pub["id"], url="https://x")
        video = self.store.get_video("t1")
        self.assertEqual(video["status"], "published")

    def test_cancelling_one_of_two_publications_keeps_video_published_if_other_survives(self):
        # This is the specific nuance the user's video_publications design was
        # meant to preserve: cancelling one publish attempt must not regress
        # the rollup status if another platform already published.
        transitions.mark_ready(self.store, "t1")
        pub_a = self.store.create_publication(video_id="t1", platform="tiktok", provider="zernio")
        pub_b = self.store.create_publication(video_id="t1", platform="youtube", provider="zernio")

        transitions.mark_publication_published(self.store, pub_a["id"], url="https://tiktok")
        self.assertEqual(self.store.get_video("t1")["status"], "published")

        transitions.cancel_publication(self.store, pub_b["id"])
        video = self.store.get_video("t1")
        self.assertEqual(video["status"], "published")
        self.assertEqual(self.store.get_publication(pub_b["id"])["status"], "cancelled")

    def test_cancel_publication_rejects_already_published_or_cancelled(self):
        transitions.mark_ready(self.store, "t1")
        pub = self.store.create_publication(video_id="t1", platform="tiktok", provider="zernio")
        transitions.mark_publication_published(self.store, pub["id"])
        with self.assertRaises(ValueError):
            transitions.cancel_publication(self.store, pub["id"])

    def test_mark_publication_failed_rolls_back_to_ready_when_no_other_publications(self):
        transitions.mark_ready(self.store, "t1")
        pub = self.store.create_publication(video_id="t1", platform="tiktok", provider="zernio")
        transitions.mark_publication_failed(self.store, pub["id"], error="upload rejected")
        video = self.store.get_video("t1")
        self.assertEqual(video["status"], "ready")
        self.assertEqual(self.store.get_publication(pub["id"])["status"], "failed")

    def test_record_re_render_appends_event_to_original_video(self):
        transitions.record_re_render(self.store, "t1", "t2")
        events = self.store.list_events("t1")
        self.assertEqual(events[0]["type"], "re_rendered")
        self.assertEqual(events[0]["data"], {"new_video_id": "t2"})

    def test_record_stage_event_never_raises_on_bad_store_state(self):
        # Fire-and-forget: even if VideoLibraryStore() can't be constructed
        # normally in a test environment, this must not raise -- it must
        # never be able to break an actual render.
        try:
            transitions.record_stage_event("nonexistent-task", "render", 0.0)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"record_stage_event raised unexpectedly: {exc}")


if __name__ == "__main__":
    unittest.main()
