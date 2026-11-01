"""Exotic leg-based settlement: dead legs settle LOST, full-house wins settle
WON only with a scraped tote dividend, everything unknown stays PENDING.

Regression context: exotics used to skip settlement entirely and queue
PENDING forever ("needs pool dividends" path never built).
"""
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.skills.result_tracker import (
    ResultTracker,
    _exotic_requirement,
    _extract_pool_dividend,
    _parse_exotic_ticket,
    _race_runners_by_number,
)

_SAST = timezone(timedelta(hours=2))


def _bet(**kw):
    b = MagicMock()
    b.bet_id = kw.get("bet_id", "20260101_EXO")
    b.track = kw.get("track", "turffontein")
    b.race_number = kw.get("race_number", 4)
    b.horse = kw.get("horse", "JACKPOT:4-5")
    b.confidence = kw.get("confidence", "EXOTIC")
    b.stake = kw.get("stake", 4.8)
    b.actual_return = 0.0
    b.date = kw.get("date", date.today().isoformat())
    b.notes = kw.get("notes", "")
    return b


def _ticket_notes(pool_type, legs):
    """legs: [(race, banker, [savers])]"""
    return json.dumps({
        "pool_type": pool_type,
        "pool_legs": [r for r, _, _ in legs],
        "combinations": [
            {"race": r, "banker": b, "savers": s} for r, b, s in legs
        ],
        "ticket_cost": 1.2,
    })


RACES = [
    {"title": "4 14:05 Turffontein Maiden", "runners": [
        {"name": "Kensal Green", "position": "1st"},
        {"name": "Pressonregardless", "position": "3rd"},
        {"name": "Also Ran", "position": "5th"},
    ]},
    {"title": "5 14:40 Turffontein Handicap", "runners": [
        {"name": "Bisou Bisou", "position": "1st"},
        {"name": "Kudikaran", "position": "4th"},
    ]},
]


@pytest.fixture()
def stub_modules():
    """Stub strike_brain + ATR parser (host CI lacks heavy deps)."""
    brain_stub = MagicMock(name="strike_brain_stub")
    brain_stub.brain = MagicMock(name="brain_stub")
    brain_stub.brain.strike = None

    class FakeATR:
        async def get_results_for_track(self, track, date="yesterday"):
            return RACES

    atr_stub = MagicMock(name="attheraces_api_stub")
    atr_stub.AtTheRacesAPI = FakeATR
    parsers_stub = MagicMock(name="parsers_pkg_stub")
    with patch.dict(sys.modules, {
        "core_agent.core.strike_brain": brain_stub,
        "core_agent.skills.parsers": parsers_stub,
        "core_agent.skills.parsers.attheraces_api": atr_stub,
    }):
        yield


@pytest.fixture()
def past_off():
    with patch.object(
        ResultTracker, "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        yield


@pytest.fixture()
def gov():
    g = MagicMock()
    g.settle_exotic_bet.return_value = True
    return g


# --- requirement mapping ----------------------------------------------------
def test_requirement_mapping():
    assert _exotic_requirement("JACKPOT") == frozenset({"1st"})
    assert _exotic_requirement("PICK 6") == frozenset({"1st"})
    assert _exotic_requirement("PICK 3") == frozenset({"1st"})
    assert _exotic_requirement("BIPOT") == frozenset({"1st", "2nd"})
    assert _exotic_requirement("PLACE ACCUMULATOR") == frozenset({"1st", "2nd", "3rd"})
    assert _exotic_requirement("MYSTERY POOL") == frozenset({"1st"})  # strict default


# --- ticket parsing ----------------------------------------------------------
def test_parse_ticket_from_notes():
    bet = _bet(notes=_ticket_notes("JACKPOT", [(4, "PRESSONREGARDLESS", ["KENSAL GREEN"])]))
    t = _parse_exotic_ticket(bet)
    assert t["pool_type"] == "JACKPOT"
    assert t["pool_legs"] == [4]
    assert t["combos"][0]["candidates"] == ["PRESSONREGARDLESS", "KENSAL GREEN"]


def test_parse_ticket_fallback_legs_only_has_no_combos():
    bet = _bet(horse="PICK6:4-5-6-7-8-9", notes="")
    t = _parse_exotic_ticket(bet)
    assert t["pool_type"] == "PICK6"
    assert t["pool_legs"] == [4, 5, 6, 7, 8, 9]
    assert t["combos"] == []


def test_parse_ticket_garbage_returns_none():
    assert _parse_exotic_ticket(_bet(horse="Silver Storm", notes="")) is None


def test_race_runners_by_number():
    assert len(_race_runners_by_number(RACES, 4)) == 3
    assert _race_runners_by_number(RACES, 9) is None


# --- dividend parsing ----------------------------------------------------------
def test_dividend_parsing_sa_format():
    assert _extract_pool_dividend("JACKPOT PAYS R1 234,50", "JACKPOT") == 1234.50
    assert _extract_pool_dividend("PICK 6 PAYOUT R250,00", "PICK 6") == 250.00
    assert _extract_pool_dividend("no dividends here", "JACKPOT") is None
    assert _extract_pool_dividend("", "JACKPOT") is None


# --- settle paths --------------------------------------------------------------
def test_jackpot_lost_when_banker_beaten(stub_modules, past_off, gov):
    bet = _bet(notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["ALSO RAN"]),  # 3rd and 5th: dead
        (5, "BISOU BISOU", ["KUDIKARAN"]),       # winner: alive, but R4 kills it
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is not None and rec["won"] is False
    gov.settle_exotic_bet.assert_called_once()
    args = gov.settle_exotic_bet.call_args[0]
    assert args[0] == bet.bet_id and args[1] == 0.0


def test_saver_win_still_passes_leg(stub_modules, past_off, gov):
    # R4 saver KENSAL GREEN won -> leg passes; R5 banker won -> ticket won,
    # but no dividend scraped -> stays PENDING (honest, no fabricated payout).
    bet = _bet(notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["KENSAL GREEN"]),
        (5, "BISOU BISOU", ["KUDIKARAN"]),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_scrape_sa_results_direct",
                      new=AsyncMock(return_value="no dividends")):
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is None
    gov.settle_exotic_bet.assert_not_called()


def test_won_settles_with_scraped_dividend(stub_modules, past_off, gov):
    bet = _bet(stake=4.8, notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["KENSAL GREEN"]),
        (5, "BISOU BISOU", ["KUDIKARAN"]),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_scrape_sa_results_direct",
                      new=AsyncMock(return_value="JACKPOT PAYS R250,00")):
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is not None and rec["won"] is True
    args = gov.settle_exotic_bet.call_args[0]
    assert args[1] == pytest.approx(250.0 * 4.8)


def test_bipot_second_place_passes_leg(stub_modules, past_off, gov):
    races = [{"title": "2 12:00 Turffontein", "runners": [
        {"name": "Some Winner", "position": "1st"},
        {"name": "Second Best", "position": "2nd"},
    ]}]

    class FakeATR2:
        async def get_results_for_track(self, track, date="yesterday"):
            return races

    atr_stub = MagicMock(name="attheraces_api_stub2")
    atr_stub.AtTheRacesAPI = FakeATR2
    bet = _bet(horse="BIPOT:2", race_number=2,
               notes=_ticket_notes("BIPOT", [(2, "SECOND BEST", [])]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.dict(sys.modules, {"core_agent.skills.parsers.attheraces_api": atr_stub}):
        with patch.object(ResultTracker, "_scrape_sa_results_direct",
                          new=AsyncMock(return_value="")):
            rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    # 2nd satisfies Bipot, no dividend -> pending, no settle call
    assert rec is None
    gov.settle_exotic_bet.assert_not_called()


def test_unknown_results_stay_pending(stub_modules, past_off, gov):
    bet = _bet(notes=_ticket_notes("JACKPOT", [(9, "GHOST HORSE", [])]))
    tracker = ResultTracker(bankroll_governor=gov)
    rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is None
    gov.settle_exotic_bet.assert_not_called()


def test_future_off_time_skipped(stub_modules, gov):
    bet = _bet(notes=_ticket_notes("JACKPOT", [(4, "KENSAL GREEN", [])]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_race_off_datetime",
                      return_value=datetime.now(_SAST) + timedelta(hours=3)):
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is None
    gov.settle_exotic_bet.assert_not_called()


def test_full_loop_settles_exotic_lost(stub_modules, past_off, gov):
    bet = _bet(notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["ALSO RAN"]),
        (5, "KUDIKARAN", ["ALSO RAN"]),
    ]))
    gov.get_open_bets.return_value = [bet]
    tracker = ResultTracker(bankroll_governor=gov)
    settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert len(settled) == 1 and settled[0]["won"] is False
    gov.settle_exotic_bet.assert_called_once()


def test_two_day_old_ticket_never_scored(stub_modules, past_off, gov):
    # ATR serves today/yesterday only: a 2-day-old ticket must stay PENDING
    # even with losing legs (Sep-2026: Sep-10 tickets scored vs Sep-12 winners).
    old = (date.today() - timedelta(days=2)).isoformat()
    bet = _bet(date=old, notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["ALSO RAN"]),
        (5, "KUDIKARAN", ["ALSO RAN"]),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is None
    gov.settle_exotic_bet.assert_not_called()


def test_duplicate_ticket_keeps_earliest(stub_modules, past_off):
    gov = MagicMock()
    gov.settle_exotic_bet.return_value = True
    notes = _ticket_notes("JACKPOT", [(4, "KENSAL GREEN", [])])
    first = _bet(bet_id="20260101_AAA", notes=notes)
    dupe = _bet(bet_id="20260101_ZZZ", notes=notes)
    gov.get_open_bets.return_value = [first, dupe]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_scrape_sa_results_direct",
                      new=AsyncMock(return_value="")):
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    # Earliest evaluated (single passing leg, no dividend -> pending, no
    # settle call); the dupe cancelled with refund, never settled.
    gov.cancel_pending_bet.assert_called_once_with(
        "20260101_ZZZ", f"duplicate of 20260101_AAA (same ticket recorded twice)")
    assert all(s["bet_id"] != "20260101_ZZZ" for s in settled)


def test_over_age_bets_expire(stub_modules):
    gov = MagicMock()
    old = (date.today() - timedelta(days=9)).isoformat()
    bet = _bet(date=old, horse="Silver Storm", confidence="VALUE")
    gov.get_open_bets.return_value = [bet]
    tracker = ResultTracker(bankroll_governor=gov)
    settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert settled == []
    gov.expire_stale_bet.assert_called_once_with(bet.bet_id)
