"""Mode 5 — faceless stock-footage automation defaults."""

from __future__ import annotations

from typing import Any

name = "faceless"

MODE_DEFAULTS: dict[str, Any] = {
    "video_aspect": "9:16",
    "video_source": "collector",
    "match_materials_to_script": True,
    "video_concat_mode": "sequential",
    "paragraph_number": 3,
    "bgm_type": "profile_random",
}
