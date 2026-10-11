"""Regression (Oct-2026, Fairview/Greyville Friday): a 09:30 rescan without
single-race plays wiped the 05:00 scan's EXA/TRI off the Hub board while the
ledger bets stayed open — and PA never appeared because convention only
applied when pool_starts was totally empty."""

import pytest

from core_agent.core.strike_tips import (
    _exotic_pool_key,
    _exotic_card_key,
    _merge_exotic_history,
    _order_names_by_live_odds,
    _deterministic_single_race_plays,
)
from core_agent.skills.exotics.builder import convention_pool_starts


def _play(pool, legs, track="fairview"):
    return {"pool": pool, "legs": legs, "_track": track}


def _play_with(pool, legs, bankers, track="greyville"):
    return {
        "pool": pool,
        "legs": legs,
        "_track": track,
        "combinations": [
            {"race": r, "banker": b, "savers": ["S1"]}
            for r, b in zip(legs, bankers)
        ],
    }


def test_pool_key_collapses_label_variants():
    assert _exotic_pool_key(_play("JP1", [4, 5, 6, 7])) == _exotic_pool_key(
        _play("JACKPOT", [4, 5, 6, 7])
    )
    assert _exotic_pool_key(_play("PA", [2, 3, 4, 5, 6, 7, 8])) == _exotic_pool_key(
        _play("PLACE ACCUMULATOR", [2, 3, 4, 5, 6, 7, 8])
    )
    assert _exotic_pool_key(_play("BI1", [1, 2, 3, 4, 5, 6])) != _exotic_pool_key(
        _play("JP1", [1, 2, 3, 4])
    )


def test_rescan_replaces_same_pool_but_keeps_missing_ones(tmp_path):
    day = "2026-10-09"
    d = str(tmp_path)
    morning = [
        _play("EXACTA", [1]),
        _play("TRIFECTA", [1]),
        _play("BI1", [1, 2, 3, 4, 5, 6]),
    ]
    board = _merge_exotic_history(d, day, morning)
    assert len(board) == 3

    # 09:30 rescan: fresh multi-leg only, AI renamed the jackpot label.
    rescan = [
        _play("BIPOT", [1, 2, 3, 4, 5, 6]),
        _play("JACKPOT", [4, 5, 6, 7]),
    ]
    board = _merge_exotic_history(d, day, rescan)
    families = sorted(_exotic_pool_key(p)[0] for p in board)
    # exactas survive, bipot replaced (not duplicated), jackpot added
    assert families == ["BIPOT", "EXACTA", "JACKPOT", "TRIFECTA"]


def test_same_pool_legs_different_bankers_both_kept(tmp_path):
    """Oct-2026 (Greyville Sunday): 05:00 AI Bipot and 09:30 fallback Bipot
    share family+legs but not bankers — the board must show BOTH."""
    day = "2026-10-11"
    d = str(tmp_path)
    legs = [2, 3, 4, 5, 6, 7]
    ai_bankers = ["Jys", "Into", "Prof", "Show", "Had", "Moh"]
    fb_bankers = ["Abbey", "Sweet", "Lupin", "Girl", "Wall", "Prince"]
    _merge_exotic_history(d, day, [_play_with("BI1", legs, ai_bankers)])
    board = _merge_exotic_history(
        d, day, [_play_with("BIPOT", legs, fb_bankers)])
    bipots = [p for p in board if _exotic_pool_key(p)[0] == "BIPOT"]
    assert len(bipots) == 2


def test_same_bankers_rescan_refreshes_in_place(tmp_path):
    day = "2026-10-11"
    d = str(tmp_path)
    legs = [2, 3, 4, 5, 6, 7]
    bankers = ["Jys", "Into", "Prof", "Show", "Had", "Moh"]
    _merge_exotic_history(d, day, [_play_with("BI1", legs, bankers)])
    board = _merge_exotic_history(d, day, [_play_with("BIPOT", legs, bankers)])
    bipots = [p for p in board if _exotic_pool_key(p)[0] == "BIPOT"]
    assert len(bipots) == 1
    assert bipots[0]["pool"] == "BIPOT"


def test_convention_covers_full_sa_slate_for_double_meeting_cards():
    starts = convention_pool_starts(8)
    for code in ("BI1", "PA", "P6", "JP1", "JP2"):
        assert code in starts, f"{code} missing from 8-race convention"
    assert starts["PA"] == 2  # TAB standard: PA R2-8


def test_live_odds_ordering_puts_favourite_first():
    odds = {"greyville": {"outsider": 21.0, "favourite": 2.5, "mid": 7.0}}
    ordered = _order_names_by_live_odds(
        ["Outsider", "Mid", "Favourite"], "Greyville", odds)
    assert ordered == ["Favourite", "Mid", "Outsider"]


def test_live_odds_ordering_unknowns_keep_card_order_at_back():
    odds = {"greyville": {"favourite": 2.5}}
    ordered = _order_names_by_live_odds(
        ["Dark Horse", "Favourite", "Mystery"], "Greyville", odds)
    assert ordered[0] == "Favourite"
    assert ordered[1:] == ["Dark Horse", "Mystery"]


def test_deterministic_single_race_builds_full_slate_without_llm():
    quals = [
        (1, [f"H{i}" for i in range(1, 10)], ["Exacta", "Trifecta"]),
        (2, [f"H{i}" for i in range(1, 10)], ["Exacta", "Trifecta"]),
        (3, [f"H{i}" for i in range(1, 13)], ["Exacta", "Trifecta", "Quartet"]),
    ]
    odds = {"greyville": {f"h{i}": float(i) for i in range(1, 13)}}
    plays = _deterministic_single_race_plays(
        quals, "greyville", odds, total_races=8)
    fams = sorted(_exotic_pool_key(p)[0] for p in plays)
    assert "TRIFECTA" in fams
    assert "QUARTET" in fams
    assert "PICK 3" in fams
    # banker is the live favourite in every ticket
    for p in plays:
        for c in p["combinations"]:
            assert c["banker"] == "H1"
