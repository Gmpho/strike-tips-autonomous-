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


# ── Two books (Nov-2026) ─────────────────────────────────────────────
# The HUD reported a 23.7% "win rate" that was 265 wins over 1,118 tickets,
# which is neither the real book (105/105 won, 698 expired) nor the paper
# book (160/1,013). Every caller now reads `books.real` / `books.paper` and
# they are never averaged into a third number.

def _paper(**kwargs):
    bet = _bet(**kwargs)
    bet["is_paper"] = True
    return bet


def test_books_split_never_blend():
    stats = compute_bet_stats([
        _bet(status="WON", stake=10.0, payout=40.0),
        _bet(status="EXPIRED", stake=10.0, payout=0.0),
        _paper(status="WON", stake=10.0, payout=20.0),
        _paper(status="LOST", stake=10.0, payout=0.0),
        _paper(status="LOST", stake=10.0, payout=0.0),
    ])
    real, paper = stats["books"]["real"], stats["books"]["paper"]

    assert real["settledBets"] == 1
    assert real["losses"] == 0
    assert real["winRate"] == 100.0
    assert real["expiredBets"] == 1
    # 698 of 803 real tickets never resolved in the live ledger: the share is
    # reported, so a 100% win rate can never be read as skill.
    assert real["unresolvedShare"] == 50.0

    assert paper["settledBets"] == 3
    assert paper["winRate"] == 33.3
    assert paper["losses"] == 2

    # The legacy flat keys still describe the whole ledger (50%, not 100/33).
    assert stats["settledBets"] == 4
    assert stats["winRate"] == 50.0


def test_calibration_reports_each_book():
    cal = compute_calibration([
        _bet(odds=2.0, stake=10.0, payout=20.0),
        _paper(odds=2.0, status="LOST", stake=10.0, payout=0.0),
        _paper(odds=2.0, status="LOST", stake=10.0, payout=0.0),
    ])
    assert cal["books"]["real"]["samples"] == 1
    assert cal["books"]["real"]["accuracy"] == 50.0
    assert cal["books"]["paper"]["samples"] == 2
    assert cal["books"]["paper"]["accuracy"] == -50.0
    # Real +74.5pp next to paper +6.3pp is the missing-losses artefact; the
    # blended figure hides both.
    assert cal["samples"] == 3


def test_track_ranking_uses_capped_roi():
    """One BIPOT must not crown a losing track.

    Turffontein's +1,540% cell was 26 winners in 175 tickets, and its top
    three tickets were 75% of the return. Ranking on raw ROI picks that track;
    capping each ticket at 10x stake picks the honest one.
    """
    from datetime import date

    bets = [_bet(track="turffontein", status="LOST", stake=5.0, payout=0.0, odds=9.0)
            for _ in range(30)]
    bets.append(_bet(track="turffontein", status="WON", stake=5.0, payout=33000.0, odds=6600.0))
    bets += [_bet(track="kenilworth", status="LOST", stake=5.0, payout=0.0, odds=3.0)
             for _ in range(10)]
    bets += [_bet(track="kenilworth", status="WON", stake=5.0, payout=12.0, odds=2.4)
             for _ in range(15)]

    res = compute_track_stats(bets, today=date(2026, 11, 1))
    turf = res["trackStats"]["Turffontein"]
    assert turf["roi"] > 1000          # the number that made it "Best Track"
    assert turf["roiCapped"] < 0       # the same ledger, one jackpot capped
    assert turf["cap"] == 10.0
    assert turf["topShare"] > 90       # one ticket is ~all of the return
    assert res["bestTrack"]["name"] == "Kenilworth"
    assert res["worstTrack"]["name"] == "Turffontein"
    # Per-track maps keep the ledger's lower-case keys (same as roiByTrack).
    assert res["roiCappedByTrack"]["turffontein"] == turf["roiCapped"]


def test_track_stats_books_are_disjoint():
    from datetime import date

    bets = [
        _bet(track="turffontein", status="WON", stake=10.0, payout=30.0),
        _paper(track="kenilworth", status="LOST", stake=10.0, payout=0.0),
    ]
    res = compute_track_stats(bets, today=date(2026, 11, 1))
    assert set(res["books"]["real"]["trackStats"]) == {"Turffontein"}
    assert set(res["books"]["paper"]["trackStats"]) == {"Kenilworth"}
    # Blended top level still lists both, for legacy consumers only.
    assert set(res["trackStats"]) == {"Turffontein", "Kenilworth"}
