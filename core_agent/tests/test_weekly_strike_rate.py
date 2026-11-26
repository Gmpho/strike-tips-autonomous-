"""The leaderboard's Top Strike Rate card must follow current activity.

A lifetime rate froze the highlight card for weeks once a leading punter
stopped tipping (26 Nov 2026: 31.7% since 22 Nov). Board rows therefore carry a
rolling weekly strike rate alongside the lifetime one; the HUD card reads the
rolling field.
"""

from core_agent.skills.league.rollups import build_board

NOW = "2026-11-26T12:00:00+00:00"  # Thursday, week starts Monday 23 Nov


def _pick(eid, won, date, pos=None):
    return {
        "entity_type": "player",
        "entity_id": eid,
        "entity_name": eid,
        "region": "SA",
        "date": date,
        "settled": True,
        "won": won,
        "points": 10 if won else 0,
        "winner_sp": 5.0,
        "pick_odds": 3.0,
        "finish_position": pos,
    }


def _row(picks, eid="a"):
    rows = build_board(picks, NOW)
    return next(r for r in rows if r["entity_id"] == eid)


def test_weekly_rate_ignores_old_picks():
    """A lifetime leader with no tips this week has nothing to crown."""
    picks = [_pick("a", True, "2026-11-10") for _ in range(20)]
    row = _row(picks)

    assert row["settled"] == 20
    assert row["strike_rate"] == 1.0
    assert row["weekly_settled"] == 0
    assert row["weekly_strike_rate"] == 0.0


def test_weekly_rate_counts_only_current_week():
    picks = (
        [_pick("a", True, "2026-11-10") for _ in range(10)]
        + [_pick("a", True, "2026-11-24")]
        + [_pick("a", False, "2026-11-25")]
    )
    row = _row(picks)

    assert row["weekly_settled"] == 2
    assert row["weekly_strike_rate"] == 0.5
    assert row["strike_rate"] == 11 / 12


def test_weekly_rate_uses_finishing_position_not_scored_flag():
    """A top-four 'scored' flag is not a win, same rule as the lifetime rate."""
    picks = [
        _pick("a", True, "2026-11-24", pos=3),
        _pick("a", True, "2026-11-24", pos=1),
    ]
    row = _row(picks)

    assert row["weekly_wins"] == 1
    assert row["weekly_strike_rate"] == 0.5


def test_weekly_rate_moves_when_new_tips_settle():
    first = _row([_pick("a", True, "2026-11-24")])
    second = _row([_pick("a", True, "2026-11-24"), _pick("a", False, "2026-11-25")])

    assert first["weekly_strike_rate"] == 1.0
    assert second["weekly_strike_rate"] == 0.5
