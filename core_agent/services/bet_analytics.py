"""
Ledger-derived betting analytics — single source of truth.

Root cause (Oct 2026): the LearningEngine's segment stats drifted from the
ledger because only the legacy `StrikeTips.settle_bet` path called
`record_result`; the auto-settler never did. The HUD then showed
turffontein at -34% while the ledger had booked +413% (today's Pick 6 was
invisible to the engine).

Everything here reads bet_history.json records and never trusts
learning_stats.json. Pure functions, no FastAPI/Modal imports.

Also fixes a survivorship-bias trap: EXPIRED tickets are refunded (not
losses), so tracks with mass expiries looked unbeatable (kenilworth: 11
settled winners out of 105 tickets, +351%). Track rankings therefore
require a minimum settled sample and a recency window.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

SETTLED_STATUSES = ("WON", "LOST")
REFUNDED_STATUSES = ("VOID", "EXPIRED")

MIN_TRACK_SAMPLE = 20
TRACK_RECENCY_DAYS = 90
MIN_TRACK_NAME_LEN = 4


def _payout(bet: Dict[str, Any]) -> float:
    """Settled return, tolerating either ledger field name."""
    value = bet.get("payout")
    if value is None:
        value = bet.get("actual_return")
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _stake(bet: Dict[str, Any]) -> float:
    try:
        return float(bet.get("stake") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _placed_date(bet: Dict[str, Any]) -> Optional[date]:
    raw = str(bet.get("placedAt") or bet.get("timestamp") or bet.get("date") or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _track(bet: Dict[str, Any]) -> str:
    return str(bet.get("track") or "").strip().lower()


def compute_bet_stats(bets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """All-time stats. VOID/EXPIRED are refunds, never 'pending'."""
    rows: List[Dict[str, Any]] = list(bets or [])
    settled = [b for b in rows if str(b.get("status") or "").upper() in SETTLED_STATUSES]
    won = [b for b in settled if str(b.get("status") or "").upper() == "WON"]
    lost = [b for b in settled if str(b.get("status") or "").upper() == "LOST"]
    pending = [b for b in rows if str(b.get("status") or "").upper() == "PENDING"]
    voided = [b for b in rows if str(b.get("status") or "").upper() == "VOID"]
    expired = [b for b in rows if str(b.get("status") or "").upper() == "EXPIRED"]

    settled_stake = sum(_stake(b) for b in settled)
    payout_total = sum(_payout(b) for b in settled)
    losing_stake = sum(_stake(b) for b in lost)
    expired_stake = sum(_stake(b) for b in expired)

    roi = ((payout_total - settled_stake) / settled_stake * 100) if settled_stake else 0.0
    # Disclosure only: what the same book would look like if every refunded
    # expired ticket had been a loss. Not a headline number (refunds are not losses).
    denom = settled_stake + expired_stake
    roi_incl = ((payout_total - denom) / denom * 100) if denom else 0.0

    return {
        "totalBets": len(rows),
        "settledBets": len(settled),
        "pendingBets": len(pending),
        "voidBets": len(voided),
        "expiredBets": len(expired),
        "wins": len(won),
        "losses": len(lost),
        "stakeTotal": round(settled_stake, 2),
        "allStakeTotal": round(sum(_stake(b) for b in rows), 2),
        "payoutTotal": round(payout_total, 2),
        "roi": round(roi, 2),
        "roiIncludingExpired": round(roi_incl, 2),
        "settlementRate": round(len(settled) / len(rows) * 100, 1) if rows else 0.0,
        "avgStake": round(settled_stake / len(settled), 2) if settled else 0.0,
        "profitFactor": round(payout_total / losing_stake, 2) if losing_stake else None,
    }


def compute_calibration(bets: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Actual win rate vs implied probability over settled bets."""
    settled = [
        b for b in (bets or [])
        if str(b.get("status") or "").upper() in SETTLED_STATUSES
    ]
    if not settled:
        return {"accuracy": 0.0, "samples": 0, "actualWinRate": 0.0, "impliedWinRate": 0.0}
    wins = sum(1 for b in settled if str(b.get("status") or "").upper() == "WON")
    actual = wins / len(settled)
    implied = sum(1.0 / max(float(b.get("odds") or 1.0), 1.01) for b in settled) / len(settled)
    return {
        "accuracy": round((actual - implied) * 100, 1),
        "samples": len(settled),
        "actualWinRate": round(actual * 100, 1),
        "impliedWinRate": round(implied * 100, 1),
    }


def compute_track_stats(
    bets: Iterable[Dict[str, Any]],
    today: Optional[date] = None,
    min_sample: int = MIN_TRACK_SAMPLE,
    recency_days: int = TRACK_RECENCY_DAYS,
) -> Dict[str, Any]:
    """ROI by track from settled bets, with sample size and recency gates."""
    today = today or date.today()
    agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "wins": 0, "staked": 0.0, "returned": 0.0, "last": None}
    )

    for bet in bets or []:
        if str(bet.get("status") or "").upper() not in SETTLED_STATUSES:
            continue
        track = _track(bet)
        if len(track) < MIN_TRACK_NAME_LEN:
            continue
        row = agg[track]
        row["n"] += 1
        row["wins"] += 1 if str(bet.get("status") or "").upper() == "WON" else 0
        row["staked"] += _stake(bet)
        row["returned"] += _payout(bet)
        stamp = _placed_date(bet)
        if stamp and (row["last"] is None or stamp > row["last"]):
            row["last"] = stamp

    details: Dict[str, Dict[str, Any]] = {}
    roi_numbers: Dict[str, float] = {}
    for track, row in agg.items():
        if row["staked"] <= 0:
            continue
        roi = (row["returned"] - row["staked"]) / row["staked"] * 100
        last = row["last"]
        days_since = (today - last).days if last else None
        recent = days_since is not None and days_since <= recency_days
        details[track] = {
            "roi": round(roi, 1),
            "n": row["n"],
            "wins": row["wins"],
            "staked": round(row["staked"], 2),
            "returned": round(row["returned"], 2),
            "lastSeen": last.isoformat() if last else None,
            "daysSince": days_since,
            "eligible": row["n"] >= min_sample and recent,
        }
        roi_numbers[track] = round(roi, 1)

    eligible = [d for d in details.values() if d["eligible"]]
    best = max(eligible, key=lambda d: d["roi"]) if eligible else None
    worst = min(eligible, key=lambda d: d["roi"]) if eligible else None

    def _named(track: str, row: Dict[str, Any]) -> Dict[str, Any]:
        return {"name": track.title(), **row}

    by_track_name = {track: row for track, row in details.items()}
    return {
        "roiByTrack": roi_numbers,
        "trackStats": {track.title(): row for track, row in details.items()},
        "bestTrack": _named(
            next(t for t, d in by_track_name.items() if d is best), best
        ) if best else None,
        "worstTrack": _named(
            next(t for t, d in by_track_name.items() if d is worst), worst
        ) if worst else None,
        "minSample": min_sample,
        "recencyDays": recency_days,
    }
