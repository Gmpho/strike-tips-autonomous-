"""SA racing-hours helpers (Oct-2026 cost work).

No South African meeting runs 23:00-05:00 SAST (night cards end ~21:30),
so overnight cron cycles are pure credit burn. Pure functions for tests.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

QUIET_START_HOUR = 23  # 23:00 SAST: monitors stand down
QUIET_END_HOUR = 5     # 05:00 SAST: monitors resume

# A zero-race snapshot older than this is an upstream hiccup, not a dark day:
# fail OPEN so the only writer that can refill it actually runs. Kept well
# above the 5-minute cron cadence so a genuine dark day still skips.
DARK_DAY_MAX_AGE_SECS = 6 * 3600


def in_quiet_hours(hour: int) -> bool:
    """True when a SAST hour falls in the overnight dead window."""
    return hour < QUIET_END_HOUR or hour >= QUIET_START_HOUR


def sast_hour() -> int:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Africa/Johannesburg")).hour


def _cache_age_secs(now: float) -> Optional[float]:
    """Age of the cache's writer time (epoch secs), or None when unknown."""
    try:
        from core_agent.core import snapshot_cache as sc

        written = getattr(sc, "_snapshot_written_at", 0.0) or 0.0
        if written <= 0:
            return None
        return max(0.0, now - written)
    except Exception:
        return None


def _snapshot_age_secs(snapshot: dict, now: float) -> Optional[float]:
    """Real age of a snapshot payload.

    ``sanitize_snapshot`` restamps ``timestamp`` on every read, so a payload
    carrying ``snapshot_source`` looks fresh even when the file behind it is
    hours old — its true age comes from the cache's writer time instead.
    """
    if snapshot.get("snapshot_source"):
        return _cache_age_secs(now)

    raw = snapshot.get("timestamp")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        then = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    try:
        if then.tzinfo is None:
            delta = datetime.now() - then
        else:
            delta = datetime.now(timezone.utc) - then
        return max(0.0, delta.total_seconds())
    except Exception:
        return None


def has_meetings_today(
    snapshot: dict | None,
    max_age_secs: Optional[float] = None,
) -> bool:
    """True when a monitor cycle should run.

    ``None``/empty/missing events normally mean a dark day, but the gate must
    never starve the only writer that can refill an empty card. It fails open
    when:

    * the empty card is stale (``DARK_DAY_MAX_AGE_SECS``) — the Oct-2026 odds
      freeze: ``sanitize_snapshot`` pruned the monitor's own file to zero at
      the end of a card, the gate honoured that copy and returned before the
      fetch, and the file stayed frozen for 14h (see
      ``tests/test_dark_day_gate.py``);
    * the last cycle recorded an upstream failure (``fetch_ok`` False) — an
      empty card from a 403/timeout is an outage, not a dark day, and skipping
      it would hide the outage until the card aged out.

    Skip (return False) only with positive evidence: a fresh, successfully
    fetched, genuinely empty card.
    """
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("events"):
        return True

    if snapshot.get("fetch_ok") is False:
        # Upstream failed on the last cycle: run again, this is not evidence
        # of a dark day — it is evidence that we have no data.
        return True

    limit = DARK_DAY_MAX_AGE_SECS if max_age_secs is None else max_age_secs
    age = _snapshot_age_secs(snapshot, time.time())
    if age is None:
        # Missing/undecodable timestamp: keep the historical behaviour.
        return False
    return age > limit
