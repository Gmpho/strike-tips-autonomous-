"""Regression (Oct-2026, Fairview/Greyville Friday): a 09:30 rescan without
single-race plays wiped the 05:00 scan's EXA/TRI off the Hub board while the
ledger bets stayed open — and PA never appeared because convention only
applied when pool_starts was totally empty."""

import pytest

from core_agent.core.strike_tips import _exotic_pool_key, _merge_exotic_history
from core_agent.skills.exotics.builder import convention_pool_starts


def _play(pool, legs, track="fairview"):
    return {"pool": pool, "legs": legs, "_track": track}


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


def test_convention_covers_full_sa_slate_for_double_meeting_cards():
    starts = convention_pool_starts(8)
    for code in ("BI1", "PA", "P6", "JP1", "JP2"):
        assert code in starts, f"{code} missing from 8-race convention"
    assert starts["PA"] == 2  # TAB standard: PA R2-8
