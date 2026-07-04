"""Pipeline music library — profiles under pipeline/assets/music/."""

from __future__ import annotations

import random
from pathlib import Path

from lib.categories import DEFAULT_MUSIC_PROFILES, music_profiles_for_category

_PIPELINE_DIR = Path(__file__).resolve().parents[1]
MUSIC_DIR = _PIPELINE_DIR / "assets" / "music"

VALID_PROFILES = frozenset({"lofi", "documentary", "city_pop", "traditional"})


def normalize_music_profiles(topic: dict) -> list[str]:
    """Read music_profiles from topic; derive from category when absent."""
    profiles = topic.get("music_profiles")
    if isinstance(profiles, list) and profiles:
        return [str(p) for p in profiles]

    legacy = topic.get("music_profile")
    if legacy:
        return [str(legacy)]

    category = topic.get("category")
    if category:
        return music_profiles_for_category(str(category))

    return list(DEFAULT_MUSIC_PROFILES)


def pick_music_profile(topic: dict) -> str:
    """Pick profile from topic pool; honors optional preferred_music when set."""
    profiles = normalize_music_profiles(topic)
    preferred = topic.get("preferred_music")
    if preferred and preferred in profiles:
        return str(preferred)
    return random.choice(profiles)


def list_music(profile: str) -> list[Path]:
    if profile not in VALID_PROFILES:
        raise ValueError(
            f"Unknown music profile: {profile!r}. "
            f"Expected one of: {', '.join(sorted(VALID_PROFILES))}"
        )

    profile_dir = MUSIC_DIR / profile
    if not profile_dir.is_dir():
        return []

    files = sorted(profile_dir.glob("*.mp3"), key=lambda p: p.name)
    return [path for path in files if path.is_file()]


def pick_random_music(profile: str) -> Path | None:
    files = list_music(profile)
    if not files:
        return None
    return random.choice(files)


def music_path_for_api(music_file: Path) -> str:
    """Relative path from project root for MoneyPrinterTurbo BGM resolution."""
    root = _PIPELINE_DIR.parent
    return str(music_file.resolve().relative_to(root.resolve()))
