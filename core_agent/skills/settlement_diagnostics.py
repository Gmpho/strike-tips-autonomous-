"""Why an exotic ticket stayed PENDING — recorded, not guessed.

`_settle_exotic_ticket` can decline to settle for six different reasons, and
before this module every one of them was a bare `return None`: the ledger showed
a stale ticket and operators had to reconstruct the cause from container logs
that had long since rotated. Each decline now writes one line naming the reason,
so "why is this still open?" is answerable from the volume.

Reasons:
    age_expired       past EXOTIC_MAX_AGE_DAYS — no source can prove its day
    unparseable       ticket has no combinations (bad legs payload)
    no_results        no day-scoped result source returned the ticket's races
    before_off_time   final leg hasn't run (plus grace) yet
    unknown_legs      results exist but at least one leg is indeterminate
    no_dividend       all legs placed, tote dividend not published/found
    settle_failed     governor refused the settlement write

This module only observes. It never settles, voids, or moves money.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("settlement-diagnostics")

FILENAME = "settlement_diagnostics.jsonl"
MAX_BYTES = 1_000_000
REASONS = frozenset(
    {
        "age_expired",
        "unparseable",
        "no_results",
        "before_off_time",
        "unknown_legs",
        "no_dividend",
        "settle_failed",
    }
)


def _path() -> Path:
    from core_agent.config.paths import DATA_DIR

    return Path(DATA_DIR) / FILENAME


def record_pending(
    bet_id: str,
    reason: str,
    detail: str = "",
    track: str = "",
    pool_type: str = "",
) -> None:
    """Append one diagnostic line and log it at INFO."""
    if reason not in REASONS:
        reason = "unknown_legs"
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bet_id": bet_id,
        "reason": reason,
        "detail": detail[:300],
        "track": track,
        "pool_type": pool_type,
    }
    logger.info(
        "exotic %s pending: %s%s", bet_id, reason, f" ({detail})" if detail else ""
    )
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            os.replace(path, str(path) + ".1")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:  # never let diagnostics break settlement
        logger.debug("diagnostics write failed: %s", exc)


def recent(limit: int = 50) -> List[Dict]:
    """Newest-first diagnostics, tolerant of a missing/rotated file."""
    try:
        path = _path()
    except Exception:
        return []
    if not path.exists():
        return []
    rows: List[Dict] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:][::-1]


def latest_by_bet(limit: int = 500) -> Dict[str, Dict]:
    """Most recent reason per bet — the shape the ops view wants."""
    out: Dict[str, Dict] = {}
    for row in reversed(recent(limit)):
        bet_id = row.get("bet_id")
        if bet_id:
            out[bet_id] = row
    return out
