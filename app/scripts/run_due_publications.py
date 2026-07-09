#!/usr/bin/env python3
"""Cron entrypoint for the Video Library's scheduled publications.

Meant to run every minute, not hourly -- the scan is a single indexed
SQLite query (status='scheduled' AND scheduled_at <= now), so the cost of
running it 60x/hour is negligible, and it avoids a worst-case ~59-minute
delay on a scheduled post. See pipeline/README.md for the crontab entry.

Usage: python3 app/scripts/run_due_publications.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT_DIR = Path(__file__).resolve().parents[2]
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from loguru import logger  # noqa: E402

from app.services.video_library_scheduler import run_due_publications  # noqa: E402


def main() -> int:
    processed = run_due_publications()
    if not processed:
        logger.info("run_due_publications: nothing due")
        return 0

    succeeded = sum(1 for p in processed if p["success"])
    failed = len(processed) - succeeded
    logger.info(f"run_due_publications: processed {len(processed)} ({succeeded} ok, {failed} failed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
