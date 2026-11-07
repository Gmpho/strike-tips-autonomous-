import pytest

from core_agent.skills.league.rollups import build_board


def _pick(eid, region, won, pts, date, sp=0.0, odds=3.0, settled=True, etype="cohort", pos=None):
    return {
        "entity_type": etype, "entity_id": eid, "entity_name": eid,
        "region": region, "date": date, "settled": settled, "won": won,
        "points": pts, "winner_sp": sp, "pick_odds": odds,
        "finish_position": pos,
    }


def test_empty():
    assert build_board([], "2026-11-04T00:00:00+00:00") == []


def test_qualification_gate():
    rows = build_board([
        _pick("a", "SA", True, 10, "2026-11-03", sp=5.0),
        _pick("a", "SA", True, 10, "2026-11-03", sp=5.0),
        _pick("a", "SA", True, 10, "2026-11-03", sp=5.0),
    ], "2026-11-04T00:00:00+00:00")
    assert len(rows) == 1
    assert rows[0]["qualified"] is False
    assert rows[0]["settled"] == 3


def test_ranking_and_ties():
    picks = []
    for i in range(6):
        picks.append(_pick("a", "SA", True, 10, "2026-11-03", sp=5.0))
    for i in range(6):
        picks.append(_pick("b", "SA", False, 0, "2026-11-03", sp=0.0))
    rows = build_board(picks, "2026-11-04T00:00:00+00:00")
    assert rows[0]["entity_id"] == "a"
    assert rows[0]["rank"] == 1
    assert rows[1]["rank"] == 2


def test_decay_flag():
    rows = build_board([
        _pick("a", "SA", True, 10, "2026-10-01", sp=5.0, etype="player") for _ in range(6)
    ], "2026-11-04T00:00:00+00:00")
    assert rows[0]["decayed"] is True


def test_pending_picks_never_score_but_keep_player_listed():
    """Open tips add no points, yet the tipster still shows on the board.

    A brand-new punter whose picks have not run yet used to vanish from the
    Players tab entirely, which read like "other users' picks are hidden".
    """
    rows = build_board([
        _pick("a", "SA", True, 10, "2026-11-03", sp=5.0, settled=False) for _ in range(6)
    ], "2026-11-04T00:00:00+00:00")
    assert len(rows) == 1
    row = rows[0]
    assert row["settled"] == 0
    assert row["pending"] == 6
    assert row["total_points"] == 0
    assert row["wins"] == 0
    assert row["qualified"] is False


def test_avatar_carried_into_row():
    avatar = {"mode": "preset", "preset": "fox", "emoji": "🦊", "url": None}
    picks = []
    for _ in range(6):
        p = _pick("uid-1", "SA", True, 10, "2026-11-03", sp=5.0, etype="player")
        p["avatar"] = avatar
        picks.append(p)
    rows = build_board(picks, "2026-11-04T00:00:00+00:00")
    assert rows[0]["avatar"] == avatar


def test_avatar_defaults_to_none_for_legacy_rows():
    picks = [_pick("uid-1", "SA", True, 10, "2026-11-03", sp=5.0, etype="player") for _ in range(6)]
    rows = build_board(picks, "2026-11-04T00:00:00+00:00")
    assert rows[0]["avatar"] is None

def test_wins_are_firsts_places_are_top_four():
    """`won` = scored (top 4); `wins` must still mean firsts only.

    Regression guard for 2026-11-06: every top-4 finish counted as a win, so a
    player with one actual winner and six places read "70% strike rate".
    """
    picks = [
        _pick("uid-1", "SA", True, 14, "2026-11-05", sp=4.0, etype="player", pos=1),
        _pick("uid-1", "SA", True, 6, "2026-11-05", etype="player", pos=2),
        _pick("uid-1", "SA", True, 3, "2026-11-05", etype="player", pos=3),
        _pick("uid-1", "SA", True, 2, "2026-11-05", etype="player", pos=4),
        _pick("uid-1", "SA", False, 0, "2026-11-05", etype="player", pos=7),
        _pick("uid-1", "SA", False, 0, "2026-11-05", etype="player", pos=None),
    ]
    rows = build_board(picks, "2026-11-06T08:00:00+00:00")
    row = next(r for r in rows if r["entity_type"] == "player")
    assert row["settled"] == 6
    assert row["wins"] == 1
    assert row["places"] == 4
    assert row["strike_rate"] == pytest.approx(1 / 6)
    assert row["place_rate"] == pytest.approx(4 / 6)
    assert row["total_points"] == 25


def test_player_not_split_across_regions():
    """A punter playing SA and UK cards is one row, not two.

    Regression guard: grouping keys used to include region, so the same
    account appeared twice on the Players tab (e.g. 1 settled/21 pts and
    3 settled/9 pts instead of one 4 settled/30 pts row).
    """
    picks = [
        _pick("uid-1", "SA", True, 21, "2026-11-05", sp=3.6, etype="player"),
        _pick("uid-1", "UK_IE", True, 9, "2026-11-05", sp=2.2, etype="player"),
        _pick("uid-1", "UK_IE", False, 0, "2026-11-05", etype="player"),
        _pick("uid-1", "SA", False, 0, "2026-11-05", etype="player"),
    ]
    rows = [r for r in build_board(picks, "2026-11-06T08:00:00+00:00")
            if r["entity_type"] == "player"]
    assert len(rows) == 1
    assert rows[0]["settled"] == 4
    assert rows[0]["wins"] == 2
    assert rows[0]["total_points"] == 30


def test_cohorts_still_region_scoped():
    rows = build_board([
        _pick("region:SA", "SA", True, 10, "2026-11-05"),
        _pick("region:UK_IE", "UK_IE", True, 10, "2026-11-05"),
    ], "2026-11-06T08:00:00+00:00")
    assert len(rows) == 2
    assert {r["entity_id"] for r in rows} == {"region:SA", "region:UK_IE"}


def test_player_form_uses_player_baseline_not_cohorts():
    """A punter's form is measured against other punters.

    Regression guard: the site average included ~2,400 cohort entries at well
    under a point per tip, so every real player saturated at the 100 cap and a
    30-pt/4-tip record looked identical to a 21-pt/5-tip one.
    """
    picks = []
    # Cohort aggregate: many settled losses, a few points — drags the average.
    picks += [_pick("region:SA", "SA", False, 0, "2026-11-05") for _ in range(200)]
    picks += [_pick("region:SA", "SA", True, 60, "2026-11-05")]
    # Player A: 4 tips, 30 pts. Player B: 6 tips, 21 pts.
    picks += [_pick("uid-a", "SA", True, 30, "2026-11-05", etype="player")]
    picks += [_pick("uid-a", "SA", False, 0, "2026-11-05", etype="player") for _ in range(3)]
    picks += [_pick("uid-b", "SA", True, 21, "2026-11-05", etype="player")]
    picks += [_pick("uid-b", "SA", False, 0, "2026-11-05", etype="player") for _ in range(5)]

    rows = {r["entity_id"]: r for r in build_board(picks, "2026-11-06T08:00:00+00:00")}

    assert rows["uid-a"]["form_rating"] < 100
    assert rows["uid-b"]["form_rating"] < rows["uid-a"]["form_rating"]
    assert rows["uid-a"]["needs"] == 1
    assert rows["uid-a"]["provisional"] is True
    assert rows["uid-a"]["qualified"] is False
    assert rows["uid-b"]["qualified"] is True
    assert rows["uid-b"]["provisional"] is False
    assert rows["uid-b"]["needs"] == 0
