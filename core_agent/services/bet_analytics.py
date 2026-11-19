"""
Ledger-derived betting analytics — single source of truth.

Root cause (Oct 2026): the LearningEngine's segment stats drifted from the
ledger because only the legacy `StrikeTips.settle_bet` path called
`record_result`; the auto-settler never did. The HUD then showed
turffontein at -34% while the ledger had booked +413% (today's Pick 6 was
invisible to the engine).

Everything here reads bet_history.json records and never trusts
learning_stats.json. Pure functions, no FastAPI/Modal imports.

Three corrections layered on top since:

1. **Survivorship bias.** EXPIRED tickets are refunded (not losses), so
   tracks with mass expiries looked unbeatable (kenilworth: 11 settled
   winners out of 105 tickets, +351%). Track rankings therefore require a
   minimum settled sample and a recency window.

2. **Two books.** The ledger holds paper tickets (`is_paper: true`, the
   simulator) and real ones. Blending them produced a 23.7% "win rate" that
   is neither book's rate, and a +337% ROI whose entire profit came from
   sub-R10 exotic lottery tickets. Every statistic is now ALSO reported per
   book (`books.real` / `books.paper`) and callers must never average the
   two. The flat top-level keys are kept only for older consumers.

3. **One ticket must not decide a track.** A single R7.20 BIPOT returning
   R33,222 was 44% of Turffontein's entire return, which is how a losing
   track (+780% raw) was crowned "Best Track". Ranking now uses a capped
   ROI — each ticket's return counts at most `ROI_TICKET_CAP` times its
   stake — which puts Turffontein at -43% and Greyville, honestly, on top.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

SETTLED_STATUSES = ("WON", "LOST")
REFUNDED_STATUSES = ("VOID", "EXPIRED")

MIN_TRACK_SAMPLE = 20
TRACK_RECENCY_DAYS = 90
MIN_TRACK_NAME_LEN = 4

# A 10x return on a settled ticket is already an outstanding result; anything
# beyond it is a pool dividend (BIPOT / PICK 6 / JACKPOT at 1,800-3,150 odds)
# and must not decide which track a punter should back at.
ROI_TICKET_CAP = 10.0

BOOKS = ("real", "paper")


def _status(bet: Dict[str, Any]) -> str:
    return str(bet.get("status") or "").upper()


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


def is_paper(bet: Dict[str, Any]) -> bool:
    """True for simulator tickets. Missing flag means real (legacy rows)."""
    return bool(bet.get("is_paper"))


def split_books(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Partition ledger rows into the two books, never to be recombined."""
    out: Dict[str, List[Dict[str, Any]]] = {"real": [], "paper": []}
    for row in rows or []:
        out["paper" if is_paper(row) else "real"].append(row)
    return out


def _book_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One book's all-time stats. VOID/EXPIRED are refunds, never 'pending'."""
    settled = [b for b in rows if _status(b) in SETTLED_STATUSES]
    won = [b for b in settled if _status(b) == "WON"]
    lost = [b for b in settled if _status(b) == "LOST"]
    pending = [b for b in rows if _status(b) == "PENDING"]
    voided = [b for b in rows if _status(b) == "VOID"]
    expired = [b for b in rows if _status(b) == "EXPIRED"]

    settled_stake = sum(_stake(b) for b in settled)
    payout_total = sum(_payout(b) for b in settled)
    losing_stake = sum(_stake(b) for b in lost)
    expired_stake = sum(_stake(b) for b in expired)

    # A "win" recorded with no stake or no return is not a proven win: the
    # real ledger has 105 WON / 0 LOST because free text may prove a win but
    # never a loss (see result_tracker), so 39 of those carry no payout at all.
    # Counted separately so no page can show 105-for-105 as a measured record.
    proven_wins = [b for b in won if _stake(b) > 0 and _payout(b) > 0]
    unproven_wins = [b for b in won if not (_stake(b) > 0 and _payout(b) > 0)]
    proven_losses = [b for b in lost if _stake(b) > 0]
    unproven_losses = [b for b in lost if _stake(b) <= 0]
    proven_settled = len(proven_wins) + len(proven_losses)

    roi = ((payout_total - settled_stake) / settled_stake * 100) if settled_stake else 0.0
    # Disclosure only: what the same book would look like if every refunded
    # expired ticket had been a loss. Not a headline number (refunds are not losses).
    denom = settled_stake + expired_stake
    roi_incl = ((payout_total - denom) / denom * 100) if denom else 0.0

    stamps = [d for d in (_placed_date(b) for b in settled) if d]
    unresolved = len(expired) + len(pending)
    measured = len(settled) + unresolved

    return {
        "totalBets": len(rows),
        "settledBets": len(settled),
        "pendingBets": len(pending),
        "voidBets": len(voided),
        "expiredBets": len(expired),
        "wins": len(won),
        "losses": len(lost),
        # Wins/losses that carry a stake and (for a win) a return. The
        # unproven remainder is disclosed, never folded into a rate.
        "provenWins": len(proven_wins),
        "provenLosses": len(proven_losses),
        "unprovenWins": len(unproven_wins),
        "unprovenLosses": len(unproven_losses),
        "provenWinRate": round(len(proven_wins) / proven_settled * 100, 1) if proven_settled else None,
        # A win rate is only meaningful against settled tickets; the label in
        # the HUD says exactly that. Reported per book, never blended.
        "winRate": round(len(won) / len(settled) * 100, 1) if settled else 0.0,
        "stakeTotal": round(settled_stake, 2),
        "allStakeTotal": round(sum(_stake(b) for b in rows), 2),
        "payoutTotal": round(payout_total, 2),
        "roi": round(roi, 2),
        "roiIncludingExpired": round(roi_incl, 2),
        "settlementRate": round(len(settled) / len(rows) * 100, 1) if rows else 0.0,
        # How much of this book never produced a result at all. A book that is
        # 87% unresolved cannot be presented as a profit figure.
        "unresolved": unresolved,
        "unresolvedShare": round(unresolved / measured * 100, 1) if measured else 0.0,
        "lastSettled": max(stamps).isoformat() if stamps else None,
        "avgStake": round(settled_stake / len(settled), 2) if settled else 0.0,
        "profitFactor": round(payout_total / losing_stake, 2) if losing_stake else None,
    }


def compute_bet_stats(bets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """All-time stats, plus the same stats per book.

    The flat keys describe the whole ledger (legacy consumers). New callers
    read `books.real` / `books.paper` and must not blend them: a punter's
    record and the simulator's lottery are different questions.
    """
    rows: List[Dict[str, Any]] = list(bets or [])
    stats = _book_summary(rows)
    books = split_books(rows)
    stats["books"] = {name: _book_summary(books[name]) for name in BOOKS}
    return stats


def _calibration(rows: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    settled = [b for b in (rows or []) if _status(b) in SETTLED_STATUSES]
    if not settled:
        return {"accuracy": 0.0, "samples": 0, "actualWinRate": 0.0, "impliedWinRate": 0.0}
    wins = sum(1 for b in settled if _status(b) == "WON")
    actual = wins / len(settled)
    implied = sum(1.0 / max(float(b.get("odds") or 1.0), 1.01) for b in settled) / len(settled)
    return {
        "accuracy": round((actual - implied) * 100, 1),
        "samples": len(settled),
        "actualWinRate": round(actual * 100, 1),
        "impliedWinRate": round(implied * 100, 1),
    }


def compute_calibration(bets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Actual win rate vs implied probability, per book as well as blended."""
    rows = list(bets or [])
    cal = _calibration(rows)
    books = split_books(rows)
    cal["books"] = {name: _calibration(books[name]) for name in BOOKS}
    return cal


def _track_stats(
    bets: Iterable[Dict[str, Any]],
    today: date,
    min_sample: int,
    recency_days: int,
) -> Dict[str, Any]:
    """ROI by track from settled bets, with sample size and recency gates."""
    agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "n": 0, "wins": 0, "staked": 0.0, "returned": 0.0, "last": None,
            "capped": 0.0, "top": None,
        }
    )

    for bet in bets or []:
        if _status(bet) not in SETTLED_STATUSES:
            continue
        track = _track(bet)
        if len(track) < MIN_TRACK_NAME_LEN:
            continue
        row = agg[track]
        stake = _stake(bet)
        returned = _payout(bet)
        row["n"] += 1
        row["wins"] += 1 if _status(bet) == "WON" else 0
        row["staked"] += stake
        row["returned"] += returned
        # Cap the *return* per ticket, not the stake: a 4,614x BIPOT is real
        # money in the ledger, but it is one jackpot, not a track's edge.
        row["capped"] += min(returned, ROI_TICKET_CAP * stake) if stake > 0 else returned
        if stake > 0 and (row["top"] is None or returned > row["top"]["returned"]):
            row["top"] = {
                "horse": str(bet.get("horse") or "")[:40],
                "stake": round(stake, 2),
                "returned": round(returned, 2),
                "odds": round(float(bet.get("odds") or 0), 2),
            }
        stamp = _placed_date(bet)
        if stamp and (row["last"] is None or stamp > row["last"]):
            row["last"] = stamp

    details: Dict[str, Dict[str, Any]] = {}
    roi_numbers: Dict[str, float] = {}
    for track, row in agg.items():
        if row["staked"] <= 0:
            continue
        roi = (row["returned"] - row["staked"]) / row["staked"] * 100
        roi_capped = (row["capped"] - row["staked"]) / row["staked"] * 100
        last = row["last"]
        days_since = (today - last).days if last else None
        recent = days_since is not None and days_since <= recency_days
        top = row["top"]
        details[track] = {
            "roi": round(roi, 1),
            # The ranking number: one jackpot can't crown a track.
            "roiCapped": round(roi_capped, 1),
            "cap": ROI_TICKET_CAP,
            "n": row["n"],
            "wins": row["wins"],
            "staked": round(row["staked"], 2),
            "returned": round(row["returned"], 2),
            "lastSeen": last.isoformat() if last else None,
            "daysSince": days_since,
            "eligible": row["n"] >= min_sample and recent,
            "topTicket": top,
            # How much of this track's return is that one ticket. 44% is a
            # warning, not a brag.
            "topShare": round(top["returned"] / row["returned"] * 100, 1)
            if top and row["returned"] > 0 else None,
        }
        roi_numbers[track] = round(roi, 1)

    eligible = [d for d in details.values() if d["eligible"]]
    best = max(eligible, key=lambda d: d["roiCapped"]) if eligible else None
    worst = min(eligible, key=lambda d: d["roiCapped"]) if eligible else None

    def _named(track: str, row: Dict[str, Any]) -> Dict[str, Any]:
        return {"name": track.title(), **row}

    by_track_name = {track: row for track, row in details.items()}
    return {
        "roiByTrack": roi_numbers,
        "roiCappedByTrack": {t: d["roiCapped"] for t, d in details.items()},
        "trackStats": {track.title(): row for track, row in details.items()},
        "bestTrack": _named(
            next(t for t, d in by_track_name.items() if d is best), best
        ) if best else None,
        "worstTrack": _named(
            next(t for t, d in by_track_name.items() if d is worst), worst
        ) if worst else None,
        "minSample": min_sample,
        "recencyDays": recency_days,
        "cap": ROI_TICKET_CAP,
    }


def compute_track_stats(
    bets: Iterable[Dict[str, Any]],
    today: Optional[date] = None,
    min_sample: int = MIN_TRACK_SAMPLE,
    recency_days: int = TRACK_RECENCY_DAYS,
) -> Dict[str, Any]:
    """ROI by track, ranked on a jackpot-capped ROI, per book as well."""
    today = today or date.today()
    rows = list(bets or [])
    result = _track_stats(rows, today, min_sample, recency_days)
    books = split_books(rows)
    result["books"] = {
        name: _track_stats(books[name], today, min_sample, recency_days)
        for name in BOOKS
    }
    return result
