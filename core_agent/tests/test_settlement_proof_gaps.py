"""Settlement proofs that were missing: pool-name aliases, a proven-unplaced
single, and a refunded scratched single-race exotic.

Nov-2026, Turffontein + Windsor card: four exotic tickets sat OPEN on a day
whose results were on record. Each had a different missing proof:

* a won ``TRIFECTA Multi`` could not find "Trifecta" in the dividend table
  (``TRIFECTAMULTI`` != ``TRIFECTA``), so a R101.04 payout waited for expiry;
* a single whose horse the card listed with a blank position after publishing
  1st-4th was read as "no evidence" instead of a proven loss;
* a single-race EXACTA whose banker was a non-runner had no VOID path, so it
  could neither settle nor expire-with-refund.

Nothing here moves money: every verdict needs structured, dated proof.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.skills.result_tracker import (
    ResultTracker,
    _clean_runner_name,
    _norm_name,
    _parse_exotic_ticket,
    _parse_raceform_dividend,
    _pool_key,
)

_SAST = timezone(timedelta(hours=2))


# --- pool names -------------------------------------------------------------
def test_pool_key_collapses_bookmaker_codes_and_raceform_names():
    assert _pool_key("TRIFECTA Multi") == _pool_key("Trifecta") == "TRIFECTA"
    assert _pool_key("PA") == _pool_key("Place Accumulator") == "PLACEACCUMULATOR"
    assert _pool_key("PLACE ACC") == "PLACEACCUMULATOR"
    assert _pool_key("BI1") == _pool_key("Bipot") == "BIPOT"
    assert _pool_key("BI2") == "BIPOT"
    assert _pool_key("JP1") == _pool_key("Jackpot") == "JACKPOT"
    assert _pool_key("JP2") == _pool_key("JP3") == "JACKPOT"
    assert _pool_key("P6") == _pool_key("Pick 6") == "PICK6"
    assert _pool_key("P3") == _pool_key("Pick 3") == "PICK3"
    assert _pool_key("EXA") == _pool_key("Exacta") == "EXACTA"
    assert _pool_key("TRIMULTI") == "TRIFECTA"
    assert _pool_key("QUA") == _pool_key("Quartet") == "QUARTET"
    # Unknown names still collapse to their own key (no accidental aliasing).
    assert _pool_key("Swinger") == "SWINGER"
    assert _pool_key("") == ""


# Raceform no longer embeds the JSON dividend rows this parser was written
# against (Nov-2026: 0 `"bet_type"` rows on a 525 KB Turffontein page) — the
# dividends are server-rendered <tr> cells. Values below are the real ones
# from Turffontein 2026-11-14.
RF_RENDERED_TURFFONTEIN = """
<div><h2>Race 5 <small class="text-muted">Handicap</small></h2>
  <table><tbody>
    <tr><td><strong>Exacta</strong></td><td>2/3</td><td>R7.30</td></tr>
    <tr><td><strong>Trifecta</strong></td><td>2/3/9</td><td>R142.20</td></tr>
  </tbody></table>
</div>
<div><h2>Race 6 <small class="text-muted">Middle Stakes</small></h2>
  <table><tbody>
    <tr><td><strong>Exacta</strong></td><td>1/4</td><td>R31.40</td></tr>
    <tr><td><strong>Trifecta</strong></td><td>1/4/2</td><td>R84.20</td></tr>
    <tr><td><strong>Quartet</strong></td><td>1/4/2/3</td><td>R622.90</td></tr>
  </tbody></table>
</div>
<div><h2>Race 9 <small class="text-muted">Handicap</small></h2>
  <table><tbody>
    <tr><td><strong>Pick 6</strong></td>
        <td>5/2/1/5/8,11/3</td><td>R51,720.80</td></tr>
    <tr><td><strong>Place Accumulator</strong></td>
        <td>2,3,4,7,10,13,14/4,5,8/2,3,9/1,2,4/1,5,6/2,8,9,11/1,3,4</td>
        <td>R42.60</td></tr>
  </tbody></table>
</div>
"""


def test_won_trifecta_multi_finds_its_rendered_dividend():
    """The ticket is stored as "TRIFECTA Multi"; Raceform prints "Trifecta"."""
    assert (
        _parse_raceform_dividend(RF_RENDERED_TURFFONTEIN, "TRIFECTA Multi", [6])
        == 84.20
    )
    assert _parse_raceform_dividend(RF_RENDERED_TURFFONTEIN, "TRI", [5]) == 142.20
    # A race with no Trifecta row must never borrow a neighbour's payout.
    assert (
        _parse_raceform_dividend(RF_RENDERED_TURFFONTEIN, "TRIFECTA Multi", [7]) is None
    )


def test_pa_dividend_only_matches_the_official_leg_range():
    """ "PA" and "Place Accumulator" are the same pool; R3-R9 was the pool
    that day, R2-R8 never existed and must stay unpaid."""
    assert (
        _parse_raceform_dividend(RF_RENDERED_TURFFONTEIN, "PA", [3, 4, 5, 6, 7, 8, 9])
        == 42.60
    )
    assert (
        _parse_raceform_dividend(
            RF_RENDERED_TURFFONTEIN, "Place Accumulator", [3, 4, 5, 6, 7, 8, 9]
        )
        == 42.60
    )
    assert (
        _parse_raceform_dividend(RF_RENDERED_TURFFONTEIN, "PA", [2, 3, 4, 5, 6, 7, 8])
        is None
    )


def test_pa_alias_does_not_leak_the_pick6_dividend():
    assert (
        _parse_raceform_dividend(RF_RENDERED_TURFFONTEIN, "PA", [4, 5, 6, 7, 8, 9])
        is None
    )


# --- structured placing -----------------------------------------------------
def _tracker():
    return ResultTracker(bankroll_governor=MagicMock())


def _placing(races, horse, race_number=5):
    tracker = _tracker()
    with patch.object(
        ResultTracker, "_exotic_leg_races", new=AsyncMock(return_value=races)
    ):
        return asyncio.run(
            tracker._structured_placing("windsor", race_number, horse, "2026-11-14")
        )


_FULL_TOP4 = [
    {
        "title": "5 13:05 Windsor Handicap",
        "runners": [
            {"name": "Jet Smart", "position": "1st"},
            {"name": "Loki's Mischief", "position": "2nd"},
            {"name": "Le Galli Bier", "position": "3rd"},
            {"name": "Joe Cotton", "position": "4th"},
            # Ran, finished outside the published 1st-4th.
            {"name": "Dangerous Touch", "position": ""},
            {"name": "Also Ran", "position": ""},
        ],
    }
]


def test_blank_position_on_a_complete_top4_card_is_a_proven_loss():
    """Windsor R5 2026-11-14: the card published 1st-4th AND listed Dangerous
    Touch with no position — proof it finished outside the top 4, not
    missing evidence. It used to stay PENDING until the 3-day cap."""
    assert _placing(_FULL_TOP4, "Dangerous Touch") == ("unplaced", "Jet Smart")


def test_blank_position_on_a_truncated_card_proves_nothing():
    """ATR cards truncate to the winners only. A listed horse with no
    position there may be 2nd-4th, so it must stay undecided."""
    truncated = [
        {
            "title": "5 13:05 Windsor Handicap",
            "runners": [
                {"name": "Jet Smart", "position": "1st"},
                {"name": "Dangerous Touch", "position": ""},
            ],
        }
    ]
    assert _placing(truncated, "Dangerous Touch") is None


def test_card_without_a_blank_runner_is_unaffected():
    assert _placing(_FULL_TOP4, "Le Galli Bier") == ("3rd", "Jet Smart")
    assert _placing(_FULL_TOP4, "Nonexistent Horse") is None


# --- ATR saddle numbers in runner names -------------------------------------
def test_saddle_number_suffix_does_not_block_a_one_word_name():
    """ATR renders every runner as "Futurewolff (1)". Feeding that to the
    token-overlap matcher scored {"futurewolff","1"} vs {"futurewolff"} =
    exactly 0.500 — under the 0.55 bar — so EVERY one-word runner on an ATR
    card was unmatchable (two-word names survived at 0.667)."""
    assert _norm_name("Futurewolff (1)") == "futurewolff"
    assert _norm_name("Gallic Victor (8)") == "gallic victor"
    assert _norm_name("Gallic Victor [8]") == "gallic victor"
    # A bare number is still part of the name (no silent aliasing).
    assert _norm_name("Horse 2") == "horse 2"

    tracker = ResultTracker(bankroll_governor=MagicMock())
    assert tracker._fuzzy_match("Futurewolff (1)", "Futurewolff") == 1.0
    assert tracker._fuzzy_match("Nuclear Force (5)", "Nuclear Force") == 1.0
    # Different horses still score 0.
    assert tracker._fuzzy_match("Futurewolff (1)", "Command Pilot") == 0.0


def test_clean_runner_name_strips_only_the_trailing_saddle_number():
    assert _clean_runner_name("Futurewolff (1)") == "Futurewolff"
    assert _clean_runner_name("Tomyris (13)") == "Tomyris"
    assert _clean_runner_name("Joe Cotton") == "Joe Cotton"
    assert _clean_runner_name("") == ""


_ATR_STYLE_NR_CARD = [
    {
        "title": "1 09:45 Turffontein Mr 74 Handicap",
        "runners": [
            {"name": "Nuclear Force (5)", "position": "1st", "non_runner": False},
            {"name": "Euphrates (3)", "position": "2nd", "non_runner": False},
            {"name": "Golden Warrior (4)", "position": "3rd", "non_runner": False},
            {"name": "Peace Treaty (2)", "position": "4th", "non_runner": False},
            {"name": "Full Go (6)", "position": "5th", "non_runner": False},
            {"name": "Futurewolff (1)", "position": "", "non_runner": True},
        ],
    }
]


def test_nr_banker_voids_on_a_real_atr_shaped_card():
    """The exact shape that hung in production: saddle-numbered names, a
    ``non_runner`` flag and a blank position."""
    gov = MagicMock()
    gov.settle_exotic_bet.return_value = True
    gov.cancel_pending_bet.return_value = True
    bet = _bet(
        notes=_ticket_notes(
            "EXACTA",
            [
                (1, "Futurewolff", ["Euphrates", "Peace Treaty"]),
            ],
        )
    )
    with patch.object(
        ResultTracker,
        "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        rec = _settle(_ATR_STYLE_NR_CARD, bet, gov)
    assert rec is not None and rec.get("void") is True
    gov.cancel_pending_bet.assert_called_once()
    gov.settle_exotic_bet.assert_not_called()


def test_trifecta_wins_against_atr_shaped_names():
    """Turffontein R6: banker TOMYRIS, savers on 2nd/3rd — with the saddle
    numbers ATR appends. Payout 84.20 x R1.20 = R101.04."""
    races = [
        {
            "title": "6 12:40 Turffontein Middle Stakes",
            "runners": [
                {"name": "Tomyris (1)", "position": "1st"},
                {"name": "Command Pilot (4)", "position": "2nd"},
                {"name": "Orange County (2)", "position": "3rd"},
                {"name": "Corrupt (3)", "position": "4th"},
                {"name": "Open Highway (8)", "position": "5th"},
            ],
        }
    ]
    gov = MagicMock()
    gov.settle_exotic_bet.return_value = True
    gov.cancel_pending_bet.return_value = True
    bet = _bet(
        bet_id="20261114031210_TRI_R6",
        horse="TRIFECTA Multi:6",
        race_number=6,
        stake=1.20,
        notes=_ticket_notes(
            "TRIFECTA Multi",
            [
                (6, "Tomyris", ["Command Pilot", "Orange County", "Corrupt"]),
            ],
        ),
    )
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(
        ResultTracker, "_raceform_dividend", new=AsyncMock(return_value=84.20)
    ), patch.object(
        ResultTracker, "_scrape_sa_results_direct", new=AsyncMock(return_value="")
    ), patch.object(
        ResultTracker,
        "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        rec = _settle(races, bet, gov)
    assert rec is not None and rec["won"] is True
    gov.settle_exotic_bet.assert_called_once()
    assert gov.settle_exotic_bet.call_args[0][1] == 101.04


# --- scratched single-race exotic -------------------------------------------
def _bet(**kw):
    b = MagicMock()
    b.bet_id = kw.get("bet_id", "20261114031211_EXA_R1")
    b.track = kw.get("track", "turffontein")
    b.race_number = kw.get("race_number", 1)
    b.horse = kw.get("horse", "EXACTA:1")
    b.confidence = kw.get("confidence", "EXOTIC")
    b.stake = kw.get("stake", 1.20)
    b.actual_return = 0.0
    b.date = kw.get("date", "2026-11-14")
    b.notes = kw.get("notes", "")
    return b


def _ticket_notes(pool_type, legs):
    """legs: [(race, banker, [savers])] — same shape record_exotic_bet writes."""
    return json.dumps(
        {
            "pool_type": pool_type,
            "pool_legs": [r for r, _b, _s in legs],
            "combinations": [{"race": r, "banker": b, "savers": s} for r, b, s in legs],
            "ticket_cost": 1.2,
        }
    )


@pytest.fixture()
def past_off():
    with patch.object(
        ResultTracker,
        "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        yield


@pytest.fixture()
def gov():
    g = MagicMock()
    g.settle_exotic_bet.return_value = True
    g.cancel_pending_bet.return_value = True
    return g


_NR_BANKER_RACE = [
    {
        "title": "1 09:45 Turffontein Mr 74 Handicap",
        "runners": [
            {"name": "Nuclear Force", "position": "1st"},
            {"name": "Euphrates", "position": "2nd"},
            {"name": "Golden Warrior", "position": "3rd"},
            {"name": "Peace Treaty", "position": "4th"},
            {"name": "Full Go", "position": "5th"},
            {"name": "Futurewolff", "position": "", "non_runner": True},
        ],
    }
]


def _settle(races, bet, gov):
    class FakeATR:
        async def get_results_for_track(self, track, date="yesterday"):
            return races

    atr_stub = MagicMock(name="atr_nr")
    atr_stub.AtTheRacesAPI = FakeATR
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.dict(
        sys.modules, {"core_agent.skills.parsers.attheraces_api": atr_stub}
    ):
        with patch.object(
            ResultTracker, "_raceform_results", new=AsyncMock(return_value=[])
        ), patch(
            "core_agent.skills.result_tracker._snapshot_favourite", return_value=None
        ):
            return asyncio.run(tracker._settle_exotic_ticket(bet, gov, None))


def test_scratched_banker_voids_and_refunds_the_single_race_exotic():
    """Turffontein R1 EXACTA 2026-11-14: banker Futurewolff was flagged
    `non_runner`. The ticket must VOID (stake refunded) — never LOST, never
    an eternal PENDING that expires with the stake gone."""
    gov = MagicMock()
    gov.settle_exotic_bet.return_value = True
    gov.cancel_pending_bet.return_value = True
    bet = _bet(
        notes=_ticket_notes(
            "EXACTA",
            [
                (1, "Futurewolff", ["Euphrates", "Peace Treaty"]),
            ],
        )
    )
    with patch.object(
        ResultTracker,
        "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        rec = _settle(_NR_BANKER_RACE, bet, gov)

    assert rec is not None and rec.get("void") is True
    assert rec.get("won") is None
    gov.cancel_pending_bet.assert_called_once()
    assert gov.cancel_pending_bet.call_args[0][0] == bet.bet_id
    gov.settle_exotic_bet.assert_not_called()


def test_blank_banker_without_nr_flag_still_holds():
    """Guard rail: a blank position alone (no non_runner flag) is missing
    data. The VOID path must not swallow that case."""
    races = [
        {
            "title": "1 09:45 Turffontein Mr 74 Handicap",
            "runners": [
                {"name": "Nuclear Force", "position": "1st"},
                {"name": "Futurewolff", "position": ""},
                {"name": "Euphrates", "position": "2nd"},
            ],
        }
    ]
    gov = MagicMock()
    gov.settle_exotic_bet.return_value = True
    gov.cancel_pending_bet.return_value = True
    bet = _bet(
        notes=_ticket_notes(
            "EXACTA",
            [
                (1, "Futurewolff", ["Euphrates"]),
            ],
        )
    )
    with patch.object(
        ResultTracker,
        "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        rec = _settle(races, bet, gov)
    assert rec is None
    gov.cancel_pending_bet.assert_not_called()
    gov.settle_exotic_bet.assert_not_called()


def test_void_is_idempotent_when_the_governor_refuses():
    """A refused refund write reports settle_failed and leaves the ticket
    open for the next cycle — never a phantom settle."""
    gov = MagicMock()
    gov.cancel_pending_bet.return_value = False
    bet = _bet(
        notes=_ticket_notes(
            "EXACTA",
            [
                (1, "Futurewolff", ["Euphrates"]),
            ],
        )
    )
    with patch.object(
        ResultTracker,
        "_race_off_datetime",
        return_value=datetime.now(_SAST) - timedelta(hours=5),
    ):
        rec = _settle(_NR_BANKER_RACE, bet, gov)
    assert rec is None
    gov.cancel_pending_bet.assert_called_once()
    gov.settle_exotic_bet.assert_not_called()


def test_exacta_ticket_parses_the_nr_banker_leg():
    bet = _bet(
        notes=_ticket_notes(
            "EXACTA",
            [
                (1, "Futurewolff", ["Euphrates", "Peace Treaty"]),
            ],
        )
    )
    t = _parse_exotic_ticket(bet)
    assert t["pool_type"] == "EXACTA"
    assert t["pool_legs"] == [1]
    assert t["combos"][0]["candidates"] == ["Futurewolff", "Euphrates", "Peace Treaty"]
