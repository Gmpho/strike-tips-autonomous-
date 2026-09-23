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
    EXOTIC_MAX_AGE_DAYS,
    ResultTracker,
    _exotic_requirement,
    _extract_pool_dividend,
    _parse_exotic_ticket,
    _parse_raceform_dividend,
    _parse_raceform_results,
    _race_runners_by_number,
    _raceform_url,
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
    # but no dividend anywhere (TAB scrape nor Raceform archive) -> stays
    # PENDING (honest, no fabricated payout).
    bet = _bet(notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["KENSAL GREEN"]),
        (5, "BISOU BISOU", ["KUDIKARAN"]),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_scrape_sa_results_direct",
                      new=AsyncMock(return_value="no dividends")), \
         patch.object(ResultTracker, "_raceform_dividend",
                      new=AsyncMock(return_value=None)):
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
                          new=AsyncMock(return_value="")), \
             patch.object(ResultTracker, "_raceform_dividend",
                          new=AsyncMock(return_value=None)):
            rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    # 2nd satisfies Bipot, no dividend anywhere -> pending, no settle call
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


def test_two_day_old_ticket_not_scored_without_own_day_results(stub_modules, past_off, gov):
    # A historical ticket is only ever scored against ITS OWN race day
    # (Raceform archive — date-addressable). With no results published for
    # that day it must stay PENDING, never guess (Sep-2026: Sep-10 tickets
    # used to be scored vs Sep-12 winners through the "yesterday" collapse).
    old = (date.today() - timedelta(days=2)).isoformat()
    bet = _bet(date=old, notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["ALSO RAN"]),
        (5, "KUDIKARAN", ["ALSO RAN"]),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_raceform_results",
                      new=AsyncMock(return_value=[])) as rf:
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is None
    gov.settle_exotic_bet.assert_not_called()
    # The bet's own ISO date is threaded — not a collapsed "yesterday" label.
    rf.assert_awaited_once_with("turffontein", old)


def test_two_day_old_ticket_settles_from_raceform_own_day(stub_modules, past_off, gov):
    # The headline fix: a multi-day-old exotic IS scored when Raceform has
    # its day — dead legs settle LOST against that day's real placings.
    old = (date.today() - timedelta(days=2)).isoformat()
    bet = _bet(date=old, notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["ALSO RAN"]),
        (5, "KUDIKARAN", ["ALSO RAN"]),
    ]))
    day_races = [
        {"title": "4 14:05 Turffontein Maiden", "runners": [
            {"name": "Dead Winner", "position": "1st"},
            {"name": "Pressonregardless", "position": "5th"},
        ]},
        {"title": "5 14:40 Turffontein Handicap", "runners": [
            {"name": "Other Winner", "position": "1st"},
            {"name": "Kudikaran", "position": "4th"},
        ]},
    ]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_raceform_results",
                      new=AsyncMock(return_value=day_races)) as rf:
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    rf.assert_awaited_once_with("turffontein", old)
    assert rec is not None and rec["won"] is False
    gov.settle_exotic_bet.assert_called_once()
    assert gov.settle_exotic_bet.call_args[0][1] == 0.0


def test_exotic_beyond_archive_window_never_scored(stub_modules, past_off, gov):
    # Past EXOTIC_MAX_AGE_DAYS no source can prove the ticket's own day:
    # the inner gate refuses before touching any results source.
    old = (date.today() - timedelta(days=EXOTIC_MAX_AGE_DAYS + 1)).isoformat()
    bet = _bet(date=old, notes=_ticket_notes("JACKPOT", [(4, "KENSAL GREEN", [])]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_raceform_results",
                      new=AsyncMock(return_value=[])) as rf:
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is None
    rf.assert_not_awaited()
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
                      new=AsyncMock(return_value="")), \
         patch.object(ResultTracker, "_raceform_dividend",
                      new=AsyncMock(return_value=None)):
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    # Earliest evaluated (single passing leg, no dividend anywhere -> pending,
    # no settle call); the dupe cancelled with refund, never settled.
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


def test_over_age_exotic_expired_in_sweep(stub_modules):
    # Beyond the archive window exotics expire like singles (no money moves).
    gov = MagicMock()
    gov.settle_exotic_bet.return_value = True
    old = (date.today() - timedelta(days=EXOTIC_MAX_AGE_DAYS + 1)).isoformat()
    bet = _bet(date=old, horse="PICK6:4-5-6-7-8-9", confidence="EXOTIC")
    gov.get_open_bets.return_value = [bet]
    tracker = ResultTracker(bankroll_governor=gov)
    settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert settled == []
    gov.expire_stale_bet.assert_called_once_with(bet.bet_id)
    gov.settle_exotic_bet.assert_not_called()


def test_exotic_within_archive_window_not_expired(stub_modules):
    # A 5-day-old exotic outlives the 3-day singles cap: the Raceform
    # archive can still score it against its own day (Sep-16..22 backlog).
    gov = MagicMock()
    old = (date.today() - timedelta(days=5)).isoformat()
    bet = _bet(date=old, horse="BIPOT:4-5", confidence="EXOTIC")
    gov.get_open_bets.return_value = [bet]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_settle_exotic_ticket",
                      new=AsyncMock(return_value=None)) as settle:
        asyncio.run(tracker.check_and_settle_open_bets())
    gov.expire_stale_bet.assert_not_called()
    settle.assert_awaited_once()


# --- WON path: Raceform structured dividend fallback --------------------------
def test_won_settles_with_raceform_dividend(stub_modules, past_off, gov):
    # TAB-format scrape finds nothing (its sources are JS shells now) but the
    # Raceform archive has the pool dividend -> WON with the real Rand value.
    bet = _bet(stake=4.8, notes=_ticket_notes("BIPOT", [
        (4, "KENSAL GREEN", []),
        (5, "BISOU BISOU", []),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(ResultTracker, "_scrape_sa_results_direct",
                      new=AsyncMock(return_value="")), \
         patch.object(ResultTracker, "_raceform_dividend",
                      new=AsyncMock(return_value=53.5)) as rf:
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is not None and rec["won"] is True
    rf.assert_awaited_once_with("turffontein", bet.date, "BIPOT", [4, 5])
    args = gov.settle_exotic_bet.call_args[0]
    assert args[0] == bet.bet_id
    assert args[1] == pytest.approx(round(53.5 * 4.8, 2))


# --- Monitor cache: same data the HUD shows, zero CF contention ---------------
def test_monitor_cache_serves_fresh_exotic_without_atr(stub_modules, past_off, gov,
                                                       tmp_path, monkeypatch):
    import core_agent.config.paths as paths

    def dead(rno, loser):
        return {
            "course": "Turffontein", "date": "today",
            "title": f"{rno} 14:0{rno} Turffontein Maiden",
            "runners": [
                {"name": "Dead Winner", "position": "1st"},
                {"name": loser, "position": "5th"},
            ],
        }

    snap = tmp_path / "atr_results_snapshot.json"
    snap.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "results": [dead(4, "Pressonregardless"), dead(5, "Kudikaran")],
    }))
    monkeypatch.setattr(paths, "ATR_RESULTS_PATH", snap)

    atr_calls = []

    class SpyATR:
        async def get_results_for_track(self, track, date="yesterday"):
            atr_calls.append((track, date))
            return []

    atr_stub = MagicMock(name="atr_spy")
    atr_stub.AtTheRacesAPI = SpyATR

    bet = _bet(notes=_ticket_notes("JACKPOT", [
        (4, "PRESSONREGARDLESS", ["ALSO RAN"]),
        (5, "KUDIKARAN", ["ALSO RAN"]),
    ]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.dict(sys.modules, {"core_agent.skills.parsers.attheraces_api": atr_stub}), \
         patch.object(ResultTracker, "_raceform_results",
                      new=AsyncMock(side_effect=AssertionError(
                          "Raceform must not be reached when the cache has the day"))):
        rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    # Cache first: ATR never dialed, Raceform never dialed.
    assert atr_calls == []
    assert rec is not None and rec["won"] is False
    gov.settle_exotic_bet.assert_called_once()


# --- Raceform parsers (shape verified against live Sep-2026 pages) ------------
RF_HTML = """
<div wire:snapshot="{&quot;racesid&quot;:137171,&quot;raceno&quot;:1,&quot;raceofftime&quot;:&quot;12:15&quot;,&quot;racedate&quot;:&quot;2026-09-22&quot;,&quot;trackname&quot;:&quot;Vaal&quot;}">
{"raceno":1,"finish":0,"horsename":"God's Country","racename":"Maiden Plate","trackname":"Vaal"}
{"raceno":1,"finish":2,"horsename":"Stilo Novo","racename":"Maiden Plate","trackname":"Vaal"}
{"raceno":1,"finish":1,"horsename":"Berry Lancer","racename":"Maiden Plate","trackname":"Vaal"}
</div>
"""

RF_DIV = """
{"bet_type":"Bipot","selections":"4,7/2,3,6/1,4,7","dividend":"53.500"}
{"bet_type":"Place Accumulator","selections":"2,3,6/1,2","dividend":"39.300"}
{"bet_type":"Pick 6","selections":"4,7/3,6,8/6","dividend":"1712.500"}
{"bet_type":"Pick 3","selections":"2/4/3","dividend":"85.100"}
{"bet_type":"Jackpot","selections":"3,6,8/6/4/6","dividend":"209.600"}
"""


def test_parse_raceform_results_positions_and_titles():
    races = _parse_raceform_results(RF_HTML, "vaal", "2026-09-22")
    assert len(races) == 1
    race = races[0]
    # Title carries "N HH:MM" — the contract with _race_runners_by_number.
    assert race["title"] == "1 12:15 Maiden Plate"
    assert race["course"] == "Vaal"
    assert race["date"] == "2026-09-22"
    runners = _race_runners_by_number(races, 1)
    assert runners is not None
    pos = {r["name"]: r["position"] for r in runners}
    # Non-finisher (finish:0) gets no ordinal — it can satisfy no pool.
    assert pos == {"God's Country": "", "Stilo Novo": "2nd", "Berry Lancer": "1st"}
    assert _race_runners_by_number(races, 9) is None


def test_parse_raceform_results_garbage_returns_empty():
    assert _parse_raceform_results("", "vaal", "2026-09-22") == []
    assert _parse_raceform_results("<html>Client Challenge</html>",
                                   "vaal", "2026-09-22") == []


def test_parse_raceform_dividend_pools():
    assert _parse_raceform_dividend(RF_DIV, "BIPOT") == 53.5
    assert _parse_raceform_dividend(RF_DIV, "PLACE ACCUMULATOR") == 39.3
    assert _parse_raceform_dividend(RF_DIV, "PICK6") == 1712.5
    assert _parse_raceform_dividend(RF_DIV, "PICK 3") == 85.1
    assert _parse_raceform_dividend(RF_DIV, "JACKPOT") == 209.6
    assert _parse_raceform_dividend(RF_DIV, "MYSTERY POOL") is None
    assert _parse_raceform_dividend("", "BIPOT") is None
    # Entity-encoded copy (wire:snapshot style) parses identically.
    assert _parse_raceform_dividend(RF_DIV.replace('"', "&quot;"), "BIPOT") == 53.5


def test_parse_raceform_dividend_rendered_row_fallback():
    page = "<td><strong>Bipot</strong></td><td>4,7/2,3,6</td><td>R53.50</td>"
    assert _parse_raceform_dividend(page, "BIPOT") == 53.5


def test_raceform_url_validation():
    assert _raceform_url("Vaal", "2026-09-16") == \
        "https://raceform.co.za/horse-racing-results/vaal/2026-09-16"
    assert _raceform_url("vaal", "2026-09-16") is not None
    assert _raceform_url("ascot;rm -rf", "2026-09-16") is None
    assert _raceform_url("vaal", "yesterday") is None
    assert _raceform_url("", "2026-09-16") is None


# --- Wrong-day guard (Raceform serves nearest meeting on no-meeting dates) ----
def test_raceform_page_date_detects_fallback():
    from core_agent.skills.result_tracker import _raceform_page_date
    # RF_HTML serves exactly 2026-09-22.
    assert _raceform_page_date(RF_HTML) == "2026-09-22"
    # Ambiguous (two meetings' data on one page) or unreadable -> None.
    assert _raceform_page_date(RF_HTML + RF_HTML.replace("2026-09-22", "2026-09-17")) is None
    assert _raceform_page_date("<html>Client Challenge</html>") is None
    assert _raceform_page_date("") is None


def test_parse_raceform_results_rejects_wrong_day_page():
    # Live repro 2026-09: GET /horse-racing-results/vaal/2026-09-16 returned
    # HTTP 200 with the 2026-09-22 card — that page must never score a
    # ticket dated 09-16 (the exact wrong-day bug this source fixes).
    assert _parse_raceform_results(RF_HTML, "vaal", "2026-09-16") == []
    # The matching day still parses.
    assert len(_parse_raceform_results(RF_HTML, "vaal", "2026-09-22")) == 1


def test_raceform_dividend_rejects_wrong_day_page(stub_modules):
    tracker = ResultTracker.__new__(ResultTracker)
    with patch.object(ResultTracker, "_raceform_page",
                      new=AsyncMock(return_value=RF_HTML + RF_DIV)):
        wrong_day = asyncio.run(
            tracker._raceform_dividend("vaal", "2026-09-16", "BIPOT"))
        right_day = asyncio.run(
            tracker._raceform_dividend("vaal", "2026-09-22", "BIPOT"))
    assert wrong_day is None  # no fabricated payout from another day's page
    assert right_day == 53.5


# --- Apostrophe-proof matching (2026-09-23 Durbanville BIPOT live bug) -----
def test_fuzzy_match_ignores_punctuation():
    tracker = ResultTracker.__new__(ResultTracker)
    # The book spells it "Captains Elect"; the ticket "Captain's Elect".
    assert tracker._fuzzy_match("Captain's Elect", "Captains Elect") == 1.0
    assert tracker._fuzzy_match("Hey Jack Your Late", "Hey Jack Youre Late") >= 0.55
    # Distinct horses still miss.
    assert tracker._fuzzy_match("One Dawn", "Cold Summer") < 0.55
    assert tracker._fuzzy_match("", "Something") == 0.0


def test_apostrophe_winner_passes_bipot_leg(stub_modules, past_off, gov):
    """Regression: source lists the winner WITHOUT the apostrophe while the
    ticket has it — the leg must pass, not die as a false dead leg."""
    races = [{"title": "1 13:07 Durbanville Maiden", "runners": [
        {"name": "Captains Elect", "position": "1st"},
        {"name": "One Dawn", "position": "3rd"},
        {"name": "Cold Summer", "position": "12th"},
    ]}]

    class FakeATR3:
        async def get_results_for_track(self, track, date="yesterday"):
            return races

    atr_stub = MagicMock(name="attheraces_api_stub3")
    atr_stub.AtTheRacesAPI = FakeATR3
    bet = _bet(horse="BIPOT:1", race_number=1, stake=7.2,
               notes=_ticket_notes("BIPOT", [
                   (1, "Captain's Elect", ["One Dawn", "Cold Summer"])]))
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.dict(sys.modules, {"core_agent.skills.parsers.attheraces_api": atr_stub}):
        with patch.object(ResultTracker, "_scrape_sa_results_direct",
                          new=AsyncMock(return_value="")), \
             patch.object(ResultTracker, "_raceform_dividend",
                          new=AsyncMock(return_value=17.40)):
            rec = asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))
    assert rec is not None and rec["won"] is True
    args = gov.settle_exotic_bet.call_args[0]
    assert args[1] == pytest.approx(17.40 * 7.2)


# --- Leg-set-matched pool dividends (2026-09-23 Jackpot live bug) ----------
RF_DIV_MULTI = """
"results":[{"137190":[[[{"raceno":7,"finish":1,"horsename":"Yamazaki"}]]]},
 {"137191":[[[{"raceno":8,"finish":1,"horsename":"Scottish Links"}]]]},
 {"137189":[[[{"raceno":6,"finish":1,"horsename":"Boozy Susie"}]]]}]
{"id":8071,"RacesID":137190,"bet_type":"Jackpot","selections":"4,6,9/5/4/1","dividend":"496.500"}
{"id":8072,"RacesID":137191,"bet_type":"Jackpot","selections":"5/4/1/1","dividend":"2257.400"}
{"id":8073,"RacesID":137189,"bet_type":"Bipot","selections":"1,8/4,5/4,9,11/4,6,7,9/5,7/3,4","dividend":"17.400"}
"""


def test_parse_raceform_dividend_matches_ticket_legs():
    # Each row pays only the ticket whose legs it exactly covers.
    assert _parse_raceform_dividend(RF_DIV_MULTI, "JACKPOT", [5, 6, 7, 8]) == 2257.4
    assert _parse_raceform_dividend(RF_DIV_MULTI, "JACKPOT", [4, 5, 6, 7]) == 496.5
    assert _parse_raceform_dividend(RF_DIV_MULTI, "BIPOT", [1, 2, 3, 4, 5, 6]) == 17.4
    # No row covers these legs — never substitute another pool's dividend.
    assert _parse_raceform_dividend(RF_DIV_MULTI, "JACKPOT", [6, 7, 8, 9]) is None
    assert _parse_raceform_dividend(RF_DIV_MULTI, "PICK 6", [3, 4, 5, 6, 7, 8]) is None
    # Legacy callers without legs keep first-match behaviour.
    assert _parse_raceform_dividend(RF_DIV_MULTI, "JACKPOT") == 496.5
    assert _parse_raceform_dividend(RF_DIV, "BIPOT") == 53.5
