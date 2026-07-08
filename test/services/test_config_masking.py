import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import config_masking  # noqa: E402


class TestConfigMasking(unittest.TestCase):
    def test_is_secret_field_matches_common_patterns(self):
        for name in ("anthropic_api_key", "speech_key", "bedrock_aws_secret_access_key", "zernio_token", "password"):
            self.assertTrue(config_masking.is_secret_field(name), name)
        for name in ("hide_log", "llm_provider", "video_language", "target_clips"):
            self.assertFalse(config_masking.is_secret_field(name), name)

    def test_mask_value_short_string_fully_masked(self):
        self.assertEqual(config_masking.mask_value("abc"), "***")

    def test_mask_value_long_string_keeps_prefix_and_suffix(self):
        masked = config_masking.mask_value("sk-ant-abcdef123456")
        self.assertEqual(masked, "sk-a***3456")
        self.assertNotIn("abcdef", masked)

    def test_mask_section_only_masks_secret_fields(self):
        section = {"llm_provider": "anthropic", "anthropic_api_key": "sk-ant-abcdef123456", "hide_log": False}
        masked = config_masking.mask_section(section)
        self.assertEqual(masked["llm_provider"], "anthropic")
        self.assertEqual(masked["hide_log"], False)
        self.assertNotEqual(masked["anthropic_api_key"], section["anthropic_api_key"])

    def test_mask_section_empty_secret_stays_empty(self):
        masked = config_masking.mask_section({"anthropic_api_key": ""})
        self.assertEqual(masked["anthropic_api_key"], "")

    def test_apply_section_patch_skips_masked_echoed_value(self):
        section = {"anthropic_api_key": "sk-ant-abcdef123456"}
        config_masking.apply_section_patch(section, {"anthropic_api_key": "sk-a***3456"})
        self.assertEqual(section["anthropic_api_key"], "sk-ant-abcdef123456")

    def test_apply_section_patch_applies_real_new_secret(self):
        section = {"anthropic_api_key": "sk-ant-abcdef123456"}
        config_masking.apply_section_patch(section, {"anthropic_api_key": "sk-ant-brandnewkey"})
        self.assertEqual(section["anthropic_api_key"], "sk-ant-brandnewkey")

    def test_apply_section_patch_applies_non_secret_fields_normally(self):
        section = {"hide_log": False}
        config_masking.apply_section_patch(section, {"hide_log": True})
        self.assertTrue(section["hide_log"])


if __name__ == "__main__":
    unittest.main()
