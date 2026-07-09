"""Thumbnail extraction for the Video Library.

No thumbnail-generation code existed anywhere in the codebase before this --
webui/cockpit.py only ever probed for an optimistic thumbnail.jpg/.png that
nothing wrote. This is the first real writer.
"""

from __future__ import annotations

import os
import subprocess

from loguru import logger

from app.utils import utils


def extract_thumbnail(video_path: str, output_path: str, offset_seconds: float = 2.0) -> bool:
    """Extract a single frame from `video_path` into `output_path` via ffmpeg.

    Tries `offset_seconds` in first; if that fails (or the video is shorter
    than the offset), retries once at frame 0.
    """
    if not os.path.isfile(video_path):
        logger.warning(f"thumbnail extraction skipped: source video not found: {video_path}")
        return False

    if _run_ffmpeg_frame_extract(video_path, output_path, offset_seconds):
        return True
    if offset_seconds != 0:
        logger.warning(
            f"thumbnail extraction at {offset_seconds}s failed for {video_path}, "
            "retrying at 0s"
        )
        return _run_ffmpeg_frame_extract(video_path, output_path, 0)
    return False


def _run_ffmpeg_frame_extract(video_path: str, output_path: str, offset_seconds: float) -> bool:
    ffmpeg_binary = utils.get_ffmpeg_binary()
    try:
        result = subprocess.run(
            [
                ffmpeg_binary,
                "-y",
                "-ss",
                str(offset_seconds),
                "-i",
                video_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                output_path,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"thumbnail extraction failed for {video_path}: {exc}")
        return False

    if result.returncode != 0 or not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        logger.warning(
            f"thumbnail extraction failed for {video_path}: "
            f"{(result.stderr or result.stdout or '').strip()[:300]}"
        )
        return False
    return True
