"""Pure scoring functions for the Strike Tips predictor league.

Only top-4 finishers score (1st/2nd/3rd/4th); the rest zero. Field size and
starting price scale the award. Everything here is pure: no I/O, no DB, no
global state.
"""
from __future__ import annotations
from typing import Optional


MIN_TIPS_TO_QUALIFY = 5
DECAY_DAYS = 7
FORM_SCALE = 50.0  # 50 = site average, 100 = double the site average
VALUE_SCALE = 100.0  # 100 = site average winner SP


def base_points(field_size: int) -> int:
    """Position points: beating a bigger field is worth more."""
    return max(1, int(field_size or 1))


def sp_bonus(sp: Optional[float]) -> int:
    """Starting-price bonus for the winner (longer odds -> larger bonus)."""
    if sp is None or sp <= 1:
        return 0
    return min(40, int(round(6 * (float(sp) - 1))))


def score_pick(field_size: int, position: int, taken_odds: float,
               winner_sp: Optional[float]) -> int:
    """League points for one pick. Top 4 (1st/2nd/3rd/4th) score; the rest zero."""
    pos = int(position or 0)
    if pos == 1:
        return base_points(field_size) + sp_bonus(winner_sp)
    if pos == 2:
        return max(1, round(base_points(field_size) * 0.5))
    if pos == 3:
        return max(1, round(base_points(field_size) * 0.25))
    if pos == 4:
        return max(1, round(base_points(field_size) * 0.125))
    return 0


def strike_rate(wins: int, settled: int) -> float:
    if settled <= 0:
        return 0.0
    return wins / settled


def form_rating(avg_points_per_tip: float, site_avg: float) -> float:
    """30-day form rating, 0-100, 50 = site average."""
    if site_avg <= 0 or avg_points_per_tip <= 0:
        return 0.0
    return max(0.0, min(100.0, FORM_SCALE * (avg_points_per_tip / site_avg)))


def value_index(avg_winner_sp: float, site_avg_winner_sp: float) -> float:
    """100 = site average winner SP; above 100 = finds better-priced winners."""
    if site_avg_winner_sp <= 0:
        return VALUE_SCALE
    if avg_winner_sp <= 0:
        return 0.0
    return VALUE_SCALE * (avg_winner_sp / site_avg_winner_sp)


def qualifies(settled: int, min_tips: int = MIN_TIPS_TO_QUALIFY) -> bool:
    return settled >= min_tips


def decayed(last_settled_iso: Optional[str], now_iso: str) -> bool:
    """True if the player has settled nothing in the last DECAY_DAYS days."""
    if not last_settled_iso:
        return True
    try:
        from datetime import datetime, timedelta, timezone
        last = datetime.fromisoformat(last_settled_iso.replace("Z", "+00:00"))
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        return (now - last) > timedelta(days=DECAY_DAYS)
    except Exception:
        return False