import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.asgi import app  # noqa: E402
from app.config import config  # noqa: E402

# Synthetic-only values -- never read/write the real config.toml (which
# holds live provider secrets in this environment).
FAKE_APP = {"llm_provider": "anthropic", "anthropic_api_key": "sk-ant-fake0000key", "hide_log": False}
FAKE_UI = {"language": "pt", "active_channel": "acme"}


class TestConfigEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.app_patcher = patch.object(config, "app", dict(FAKE_APP))
        self.ui_patcher = patch.object(config, "ui", dict(FAKE_UI))
        self.app_patcher.start()
        self.ui_patcher.start()
        self.addCleanup(self.app_patcher.stop)
        self.addCleanup(self.ui_patcher.stop)

    def test_get_config_masks_secret_fields(self):
        response = self.client.get("/api/v1/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["app"]["llm_provider"], "anthropic")
        self.assertNotEqual(data["app"]["anthropic_api_key"], FAKE_APP["anthropic_api_key"])
        self.assertEqual(data["ui"]["language"], "pt")

    def test_put_config_updates_non_secret_field(self):
        with patch.object(config, "save_config") as mock_save:
            response = self.client.put("/api/v1/config", json={"ui": {"language": "en"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(config.ui["language"], "en")
        mock_save.assert_called_once()

    def test_put_config_echoing_masked_secret_does_not_overwrite(self):
        get_response = self.client.get("/api/v1/config")
        masked_key = get_response.json()["data"]["app"]["anthropic_api_key"]

        with patch.object(config, "save_config"):
            self.client.put("/api/v1/config", json={"app": {"anthropic_api_key": masked_key}})

        self.assertEqual(config.app["anthropic_api_key"], FAKE_APP["anthropic_api_key"])

    def test_put_config_real_new_secret_is_applied(self):
        with patch.object(config, "save_config"):
            self.client.put("/api/v1/config", json={"app": {"anthropic_api_key": "sk-ant-brandnewfakekey"}})

        self.assertEqual(config.app["anthropic_api_key"], "sk-ant-brandnewfakekey")


if __name__ == "__main__":
    unittest.main()
