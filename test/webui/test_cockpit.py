import os
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

    def test_assign_model_fields_skips_unknown_fields(self):
        class DummyModel:
            model_fields = {"known": object()}

            def __init__(self):
                self.known = "old"

        model = DummyModel()
        cockpit.assign_model_fields(model, known="new", missing="ignored")
        self.assertEqual(model.known, "new")
        self.assertFalse(hasattr(model, "missing"))

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

    def test_llm_readiness_bedrock_ready_with_model_and_region(self):
        from app.config import config

        original = dict(config.app)
        try:
            config.app["llm_provider"] = "bedrock"
            config.app["bedrock_model_name"] = "anthropic.claude-3-5-sonnet-20241022-v2:0"
            config.app["bedrock_region"] = "us-east-1"
            config.app.pop("bedrock_api_key", None)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
                status, detail = cockpit._llm_readiness(lambda key: key)
            self.assertEqual(status, "Cockpit Status Ready")
            self.assertEqual(detail, "Cockpit LLM IAM Role")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_llm_readiness_bedrock_ready_with_api_key(self):
        from app.config import config

        original = dict(config.app)
        try:
            config.app["llm_provider"] = "bedrock"
            config.app["bedrock_model_name"] = "anthropic.claude-3-5-sonnet-20241022-v2:0"
            config.app["bedrock_region"] = "us-east-1"
            config.app["bedrock_api_key"] = "ABSK_test"
            status, detail = cockpit._llm_readiness(lambda key: key)
            self.assertEqual(status, "Cockpit Status Ready")
            self.assertEqual(detail, "bedrock")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_llm_readiness_bedrock_mantle_ready_with_api_key(self):
        from app.config import config

        original = dict(config.app)
        try:
            config.app["llm_provider"] = "bedrock"
            config.app["bedrock_model_name"] = "openai.gpt-5.4"
            config.app["bedrock_region"] = "us-east-2"
            config.app["bedrock_api_key"] = "ABSK_test"
            status, detail = cockpit._llm_readiness(lambda key: key)
            self.assertEqual(status, "Cockpit Status Ready")
            self.assertEqual(detail, "bedrock")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_llm_readiness_bedrock_mantle_blocks_wrong_region(self):
        from app.config import config

        original = dict(config.app)
        try:
            config.app["llm_provider"] = "bedrock"
            config.app["bedrock_model_name"] = "openai.gpt-5.4"
            config.app["bedrock_region"] = "us-east-1"
            config.app["bedrock_api_key"] = "ABSK_test"
            status, detail = cockpit._llm_readiness(lambda key: key)
            self.assertEqual(status, "Cockpit Status Blocked")
            self.assertEqual(detail, "Cockpit Bedrock Mantle Region")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_llm_readiness_bedrock_mantle_requires_api_key(self):
        from app.config import config

        original = dict(config.app)
        try:
            config.app["llm_provider"] = "bedrock"
            config.app["bedrock_model_name"] = "openai.gpt-5.4"
            config.app["bedrock_region"] = "us-east-2"
            config.app.pop("bedrock_api_key", None)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
                status, detail = cockpit._llm_readiness(lambda key: key)
            self.assertEqual(status, "Cockpit Status Blocked")
            self.assertEqual(detail, "Cockpit Bedrock Mantle Key Required")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_llm_readiness_litellm_ready_with_model(self):
        from app.config import config

        original = dict(config.app)
        try:
            config.app["llm_provider"] = "litellm"
            config.app["litellm_model_name"] = "openai/gpt-4o-mini"
            status, detail = cockpit._llm_readiness(lambda key: key)
            self.assertEqual(status, "Cockpit Status Ready")
            self.assertEqual(detail, "litellm")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_build_runtime_config_maps_japao_fields(self):
        runtime = cockpit.build_runtime_config("japao")
        self.assertEqual(runtime["slug"], "japao")
        self.assertIn("video_source", runtime)
        self.assertIn("voice_name", runtime)
        self.assertIn("target_duration", runtime)
        self.assertTrue(runtime["match_materials_to_script"])

    def test_detect_overrides_empty_when_matching(self):
        runtime = cockpit.build_runtime_config("japao")
        form = dict(runtime)
        overrides = cockpit.detect_overrides(runtime, form)
        self.assertEqual(overrides, {})

    def test_detect_overrides_finds_voice_change(self):
        runtime = cockpit.build_runtime_config("japao")
        form = dict(runtime)
        form["voice_name"] = "pt-BR-FranciscaNeural-Female"
        overrides = cockpit.detect_overrides(runtime, form)
        self.assertIn("voice_name", overrides)

    def test_apply_runtime_config_resets_overrides(self):
        import streamlit as st

        st.session_state.clear()
        runtime = cockpit.build_runtime_config("japao")
        cockpit.apply_runtime_config(runtime, "japao")
        self.assertEqual(st.session_state.get("channel_overrides"), set())
        self.assertEqual(st.session_state.get("active_channel"), "japao")

    def test_pipeline_step_labels_has_six_steps(self):
        labels = cockpit.pipeline_step_labels(lambda key: key)
        self.assertEqual(len(labels), 6)
        self.assertEqual(cockpit.PIPELINE_STEP_COUNT, 6)

    def test_compute_pipeline_step_states_marks_idea_done(self):
        import streamlit as st

        st.session_state.clear()
        st.session_state["video_subject"] = "Hotéis cápsula"
        states = cockpit.compute_pipeline_step_states(video_source="collector")
        self.assertEqual(states[0], "done")

    def test_save_collector_job_snapshot_sets_cache_hit(self):
        import streamlit as st

        st.session_state.clear()
        if not isinstance(st.session_state, dict):
            st.session_state = {}
        cockpit.save_collector_job_snapshot(
            {
                "job_id": "job-1",
                "status": "ready",
                "local_reused": 18,
                "new_downloads": 2,
                "selected_clips_count": 20,
            }
        )
        job = st.session_state["last_collector_job"]
        self.assertEqual(job["cache_hit_pct"], 90)

    def test_count_keywords_helper(self):
        self.assertEqual(cockpit._count_keywords("a, b, c"), 3)
        self.assertEqual(cockpit._count_keywords(""), 0)


if __name__ == "__main__":
    unittest.main()
