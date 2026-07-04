import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import bgm
from app.utils import utils


class TestBgmService(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_list_profiles_reads_configured_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "lofi").mkdir()
            Path(temp_dir, "documentary").mkdir()
            config.app["bgm_profile_music_dir"] = temp_dir

            profiles = bgm.list_profiles()

        self.assertEqual(profiles, ["documentary", "lofi"])

    def test_list_tracks_returns_supported_audio_files_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir, "lofi")
            profile_dir.mkdir()
            Path(profile_dir, "a.mp3").write_bytes(b"fake")
            Path(profile_dir, "b.wav").write_bytes(b"fake")
            Path(profile_dir, "notes.txt").write_text("ignore", encoding="utf-8")
            config.app["bgm_profile_music_dir"] = temp_dir

            tracks = bgm.list_tracks("lofi")

        self.assertEqual([path.name for path in tracks], ["a.mp3", "b.wav"])

    def test_pick_random_track_returns_empty_for_missing_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config.app["bgm_profile_music_dir"] = temp_dir

            track = bgm.pick_random_track("missing")

        self.assertEqual(track, "")

    def test_resolve_bgm_profile_random_returns_track_from_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir, "lofi")
            profile_dir.mkdir()
            track_path = profile_dir / "lofi_001.mp3"
            track_path.write_bytes(b"fake")
            config.app["bgm_profile_music_dir"] = temp_dir

            with patch("app.services.bgm.random.choice", return_value=str(track_path)):
                resolved = bgm.resolve_bgm(
                    bgm_type="profile_random",
                    bgm_profile="lofi",
                )

        self.assertEqual(resolved, str(track_path))

    def test_resolve_bgm_random_still_uses_resource_songs(self):
        song_dir = utils.song_dir()
        bgm_path = Path(song_dir) / "test-random-bgm.mp3"
        bgm_path.write_bytes(b"fake")
        try:
            with patch("app.services.bgm.random.choice", return_value=str(bgm_path)):
                resolved = bgm.resolve_bgm(bgm_type="random")
        finally:
            if bgm_path.exists():
                bgm_path.unlink()

        self.assertEqual(resolved, str(bgm_path))

    def test_env_override_takes_precedence_for_profile_music_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "city_pop").mkdir()
            config.app["bgm_profile_music_dir"] = "/tmp/ignored-by-env"

            with patch.dict(os.environ, {"BGM_PROFILE_MUSIC_DIR": temp_dir}, clear=False):
                profiles = bgm.list_profiles()

        self.assertEqual(profiles, ["city_pop"])


if __name__ == "__main__":
    unittest.main()
