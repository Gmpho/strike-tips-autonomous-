"""SA racing-hours helpers (Oct-2026 cost work).

No South African meeting runs 23:00-05:00 SAST (night cards end ~21:30),
so overnight cron cycles are pure credit burn. Pure functions for tests.
"""
from __future__ import annotations

QUIET_START_HOUR = 23  # 23:00 SAST: monitors stand down
QUIET_END_HOUR = 5     # 05:00 SAST: monitors resume


def in_quiet_hours(hour: int) -> bool:
    """True when a SAST hour falls in the overnight dead window."""
    return hour < QUIET_END_HOUR or hour >= QUIET_START_HOUR


def sast_hour() -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Africa/Johannesburg")).hour
