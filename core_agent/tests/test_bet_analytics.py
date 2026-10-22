"""Ledger-derived analytics + engine rebuild (Oct-2026).

Guards the two defects found after the HUD showed kenilworth at +351% while
it had 94 refunded expiries and only 11 settled winners, and after the
learning engine reported turffontein at -34% against a +413% ledger.
"""

import json
import os

from core_agent.services.bet_analytics import (
    compute_bet_stats,
    compute_calibration,
    compute_track_stats,
)
from core_agent.skills.learning.engine import LearningEngine


def _bet(track="turffontein", status="WON", stake=10.0, payout=30.0, odds=3.0,
         distance=1450, placed="2026-10-20T09:00:00"):
    return {
        "track": track,
        "status": status,
        "stake": stake,
        "payout": payout,
        "odds": odds,
        "distance": distance,
        "placedAt": placed,
    }


def test_pending_excludes_void_and_expired():
    stats = compute_bet_stats([
        _bet(status="WON"),
        _bet(status="LOST", payout=0.0),
        _bet(status="PENDING", payout=None),
        _bet(status="VOID", payout=0.0),
        _bet(status="EXPIRED", payout=0.0),
    ])
    assert stats["totalBets"] == 5
    assert stats["settledBets"] == 2
    assert stats["pendingBets"] == 1
    assert stats["voidBets"] == 1
    assert stats["expiredBets"] == 1


def test_profit_factor_and_roi():
    stats = compute_bet_stats([
        _bet(stake=10.0, payout=40.0),
        _bet(status="LOST", stake=10.0, payout=0.0),
    ])
    assert stats["profitFactor"] == 4.0  # 40 returned / 10 lost stake
    assert stats["roi"] == 100.0
    assert stats["avgStake"] == 10.0


def test_profit_factor_none_without_losses():
    stats = compute_bet_stats([_bet(stake=10.0, payout=20.0)])
    assert stats["profitFactor"] is None


def test_roi_including_expired_is_disclosure_only():
    stats = compute_bet_stats([
        _bet(stake=10.0, payout=20.0),          # +100% on settled
        _bet(status="EXPIRED", payout=0.0),     # refunded, shown as loss only here
    ])
    assert stats["roi"] == 100.0
    assert stats["roiIncludingExpired"] == 0.0


def test_expired_winners_do_not_inflate_track_roi_into_ranking():
    """kenilworth: 11 settled winners, 94 expired -> must fail the sample gate."""
    bets = [_bet(track="kenilworth", stake=6.0, payout=30.0, placed="2026-08-15T09:00:00") for _ in range(11)]
    bets += [_bet(track="kenilworth", status="EXPIRED", payout=0.0, placed="2026-09-01T09:00:00") for _ in range(94)]
    bets += [_bet(track="turffontein", stake=40.0, payout=200.0) for _ in range(25)]
    result = compute_track_stats(bets, today=__import__("datetime").date(2026, 10, 22))
    assert result["trackStats"]["Kenilworth"]["n"] == 11
    assert result["trackStats"]["Kenilworth"]["eligible"] is False
    assert result["bestTrack"]["name"] == "Turffontein"


def test_recency_gate_disqualifies_stale_tracks():
    import datetime
    bets = [_bet(track="greyville", stake=10.0, payout=30.0, placed="2026-01-10T09:00:00") for _ in range(30)]
    result = compute_track_stats(bets, today=datetime.date(2026, 10, 22))
    assert result["trackStats"]["Greyville"]["eligible"] is False
    assert result["bestTrack"] is None


def test_junk_track_keys_are_dropped():
    bets = [_bet(track="f", stake=6.0, payout=0.0) for _ in range(2)]
    result = compute_track_stats(bets)
    assert result["roiByTrack"] == {}


def test_calibration_compares_actual_to_implied():
    bets = [_bet(odds=2.0, stake=10.0, payout=20.0) for _ in range(2)]
    cal = compute_calibration(bets)
    assert cal["samples"] == 2
    assert cal["actualWinRate"] == 100.0
    assert cal["impliedWinRate"] == 50.0
    assert cal["accuracy"] == 50.0


def test_engine_rebuilds_from_ledger_and_keeps_dream_priors(tmp_path):
    data_dir = str(tmp_path)
    with open(os.path.join(data_dir, "bet_history.json"), "w") as f:
        json.dump([
            _bet(status="WON", stake=10.0, payout=50.0, odds=5.0),
            _bet(status="LOST", stake=10.0, payout=0.0, odds=5.0),
            _bet(status="VOID", payout=0.0, odds=5.0),
        ], f)
    with open(os.path.join(data_dir, "learning_stats.json"), "w") as f:
        json.dump({"durbanville:any:mid": {"bets": 0, "wins": 0, "dream_bets": 7, "dream_wins": 3}}, f)

    engine = LearningEngine(data_dir=data_dir)
    assert engine.refresh_from_ledger(force=True) is True

    segment = engine._stats["turffontein:mile:mid"]
    assert segment["bets"] == 2
    assert segment["wins"] == 1
    assert segment["total_staked"] == 20.0
    assert segment["total_returned"] == 50.0
    assert engine._stats["durbanville:any:mid"]["dream_bets"] == 7
