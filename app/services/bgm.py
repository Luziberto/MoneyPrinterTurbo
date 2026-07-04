import os
import random
from pathlib import Path

from loguru import logger

from app.config import config
from app.utils import file_security, utils

_BGM_EXTENSIONS = (".mp3", ".wav", ".flac")


def _resolve_profile_music_dir() -> str:
    configured_dir = os.getenv(
        "BGM_PROFILE_MUSIC_DIR",
        str(config.app.get("bgm_profile_music_dir", "pipeline/assets/music") or "").strip(),
    )
    if not configured_dir:
        return ""
    if not os.path.isabs(configured_dir):
        configured_dir = os.path.join(utils.root_dir(), configured_dir)
    return os.path.realpath(configured_dir)


def profile_music_dir() -> str:
    return _resolve_profile_music_dir()


def allowed_bgm_directories() -> list[str]:
    allowed = [utils.song_dir()]
    profile_dir = profile_music_dir()
    if profile_dir and os.path.isdir(profile_dir):
        allowed.append(profile_dir)
    return allowed


def list_profiles() -> list[str]:
    base_dir = profile_music_dir()
    if not base_dir or not os.path.isdir(base_dir):
        return []

    profiles: list[str] = []
    for entry in sorted(Path(base_dir).iterdir(), key=lambda item: item.name.lower()):
        if entry.is_dir():
            profiles.append(entry.name)
    return profiles


def list_tracks(profile: str) -> list[Path]:
    base_dir = profile_music_dir()
    if not base_dir or not os.path.isdir(base_dir):
        return []

    try:
        profile_dir = file_security.resolve_path_within_directory(
            base_dir,
            profile,
            require_file=False,
        )
    except ValueError:
        return []

    if not os.path.isdir(profile_dir):
        return []

    files = sorted(Path(profile_dir).iterdir(), key=lambda item: item.name.lower())
    return [
        path
        for path in files
        if path.is_file() and path.suffix.lower() in _BGM_EXTENSIONS
    ]


def pick_random_track(profile: str) -> str:
    tracks = list_tracks(profile)
    if not tracks:
        return ""
    return str(random.choice(tracks))


def _resolve_explicit_bgm_file(bgm_file: str) -> str:
    last_error: ValueError | None = None
    project_relative_file = (
        bgm_file if os.path.isabs(bgm_file) else os.path.join(utils.root_dir(), bgm_file)
    )

    for base_dir in allowed_bgm_directories():
        for candidate in (bgm_file, project_relative_file):
            try:
                resolved = file_security.resolve_path_within_directory(base_dir, candidate)
            except ValueError as exc:
                last_error = exc
                continue

            if not resolved.lower().endswith(_BGM_EXTENSIONS):
                logger.warning(f"reject unsupported bgm file extension: {resolved}")
                return ""
            return resolved

    if last_error is not None:
        logger.warning(
            f"reject unsafe bgm file: {bgm_file}, allowed_dirs: {allowed_bgm_directories()}, error: {str(last_error)}"
        )
    return ""


def _resolve_random_song() -> str:
    song_dir = utils.song_dir()
    files = [
        str(path)
        for path in Path(song_dir).glob("*")
        if path.is_file() and path.suffix.lower() in _BGM_EXTENSIONS
    ]
    if not files:
        logger.warning(f"no bgm files found in song directory: {song_dir}")
        return ""
    return random.choice(files)


def _resolve_profile_random(profile: str) -> str:
    if not profile:
        logger.warning("bgm_type=profile_random requires bgm_profile")
        return ""

    track = pick_random_track(profile)
    if not track:
        logger.warning(
            f"no bgm tracks found for profile: {profile}, dir: {profile_music_dir()}"
        )
        return ""
    return track


def resolve_bgm(
    params=None,
    *,
    bgm_type: str = "random",
    bgm_file: str = "",
    bgm_profile: str = "",
) -> str:
    if params is not None:
        bgm_type = getattr(params, "bgm_type", bgm_type)
        bgm_file = getattr(params, "bgm_file", bgm_file)
        bgm_profile = getattr(params, "bgm_profile", bgm_profile)

    if not bgm_type:
        return ""

    if bgm_file:
        return _resolve_explicit_bgm_file(bgm_file)

    if bgm_type == "random":
        return _resolve_random_song()

    if bgm_type == "profile_random":
        return _resolve_profile_random(bgm_profile)

    return ""
