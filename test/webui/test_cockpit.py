import unittest
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "webui"))

if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = MagicMock()

from webui import cockpit


class TestCockpitHelpers(unittest.TestCase):
    def test_list_available_channels_includes_japao(self):
        channels = cockpit.list_available_channels()
        self.assertIn("japao", channels)

    def test_load_channel_config_has_script_prompt(self):
        channel = cockpit.load_channel_config("japao")
        self.assertEqual(channel["slug"], "japao")
        self.assertIn("curiosidade", channel.get("video_script_prompt", "").lower())

    def test_scan_disk_tasks_empty_dir(self):
        rows = cockpit._scan_disk_tasks(str(ROOT / "storage" / "tasks-missing"), limit=5)
        self.assertEqual(rows, [])

    def test_analyze_clip_materials_detects_repetition(self):
        materials = [
            {"path": "/clips/a.mp4"},
            {"path": "/clips/a.mp4"},
            {"path": "/clips/b.mp4"},
        ]
        diagnosis = cockpit.analyze_clip_materials(materials)
        self.assertEqual(diagnosis["total_segments"], 3)
        self.assertEqual(diagnosis["unique_sources"], 2)
        self.assertIn("repeated_sources", diagnosis["warnings"])
        self.assertEqual(diagnosis["repeated_sources"]["/clips/a.mp4"], 2)

    def test_analyze_clip_materials_handles_string_paths(self):
        diagnosis = cockpit.analyze_clip_materials(["a.mp4", "b.mp4"])
        self.assertEqual(diagnosis["unique_sources"], 2)
        self.assertEqual(diagnosis["warnings"], [])

    @patch.object(cockpit, "_ffmpeg_readiness", return_value=("Cockpit Status Ready", "ffmpeg"))
    @patch.object(cockpit, "_tts_readiness", return_value=("Cockpit Status Ready", "voice"))
    @patch.object(cockpit, "_llm_readiness", return_value=("Cockpit Status Ready", "openai"))
    @patch.object(
        cockpit,
        "_collector_readiness",
        return_value=("Cockpit Status Blocked", "Cockpit Collector No URL"),
    )
    def test_list_render_blockers_flags_collector_without_url(
        self,
        _collector,
        _llm,
        _tts,
        _ffmpeg,
    ):
        blockers = cockpit.list_render_blockers(
            "collector",
            "pt-BR-AntonioNeural-Male",
            lambda key: key,
        )
        self.assertEqual(blockers, ["Collector — Cockpit Collector No URL"])


if __name__ == "__main__":
    unittest.main()
