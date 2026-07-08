import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import Workspace, WorkspacePatch
from app.services import workspace_store


class TestWorkspaceStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patcher = patch(
            "app.services.workspace_store._workspace_dir",
            return_value=Path(self._tmp.name),
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_load_workspace_creates_and_seeds_when_missing(self):
        seed = {"script": {"video_subject": "Kyoto"}}
        workspace = workspace_store.load_workspace("acme", seed=seed)
        self.assertEqual(workspace.channel_slug, "acme")
        self.assertEqual(workspace.script.video_subject, "Kyoto")
        self.assertTrue((Path(self._tmp.name) / "acme.json").is_file())

    def test_load_workspace_reads_back_persisted_state(self):
        workspace_store.load_workspace("acme", seed={"script": {"video_subject": "Kyoto"}})
        reloaded = workspace_store.load_workspace("acme")
        self.assertEqual(reloaded.script.video_subject, "Kyoto")

    def test_patch_workspace_deep_merges_without_clobbering_siblings(self):
        workspace_store.load_workspace(
            "acme", seed={"script": {"video_subject": "Kyoto", "video_language": "pt-BR"}}
        )
        patch_body = WorkspacePatch(script={"video_subject": "Osaka"})
        updated = workspace_store.patch_workspace("acme", patch_body)
        self.assertEqual(updated.script.video_subject, "Osaka")
        self.assertEqual(updated.script.video_language, "pt-BR")

    def test_patch_workspace_updates_updated_at(self):
        workspace_store.load_workspace("acme")
        first = workspace_store.patch_workspace("acme", WorkspacePatch(active_step=1))
        self.assertIsNotNone(first.updated_at)
        self.assertEqual(first.active_step, 1)

    def test_reset_workspace_clears_overrides_and_preview(self):
        workspace_store.load_workspace("acme")
        workspace = workspace_store.patch_workspace(
            "acme", WorkspacePatch(script={"video_subject": "Osaka"})
        )
        workspace.overrides = ["video_subject"]
        workspace.preview.ready = True
        workspace_store.save_workspace(workspace)

        reset = workspace_store.reset_workspace("acme", seed={"script": {"video_subject": "Kyoto"}})
        self.assertEqual(reset.overrides, [])
        self.assertFalse(reset.preview.ready)
        self.assertEqual(reset.script.video_subject, "Kyoto")

    def test_invalid_slug_rejected(self):
        with self.assertRaises(ValueError):
            workspace_store.load_workspace("../etc/passwd")

    def test_unassigned_slug_used_when_none(self):
        workspace = workspace_store.load_workspace(None)
        self.assertIsNone(workspace.channel_slug)
        self.assertTrue((Path(self._tmp.name) / "_unassigned.json").is_file())

    def test_save_workspace_round_trips_nested_keywords(self):
        from app.models.schema import CollectorKeyword

        workspace = Workspace(channel_slug="acme")
        workspace.keywords.terms = [CollectorKeyword(term="temple", weight=0.8)]
        workspace_store.save_workspace(workspace)
        reloaded = workspace_store.load_workspace("acme")
        self.assertEqual(len(reloaded.keywords.terms), 1)
        self.assertEqual(reloaded.keywords.terms[0].term, "temple")


if __name__ == "__main__":
    unittest.main()
