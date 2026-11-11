"""Structured racecard feed (phumelelaV4) — pure parsing tests over fixtures."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import List

import pytest

from core_agent.skills.parsers.racecard_api import (
    _claim,
    _display_name,
    _jurisdiction,
    _map_race,
    _map_runner,
    _money,
    _normalise_date,
    _parse_distance_m,
    _race_time,
    _safe_int,
    _to_decimal,
    is_racecard_program,
    parse_programs,
    parse_racecard,
)
from core_agent.skills.parsers.tab4racing import ScrapedRunner


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _all_runners(races) -> List[ScrapedRunner]:
    return [runner for race in races for runner in race.runners]


# --------------------------------------------------------------------------
# Error paths — the feed degrades to an empty card, never raises.
# --------------------------------------------------------------------------


def test_racecard_error_payload_returns_empty():
    assert parse_racecard({"error": 1, "message": "boom"}) == []


def test_racecard_non_dict_payload_returns_empty():
    assert parse_racecard("notadict") == []


def test_racecard_empty_result_returns_empty():
    assert parse_racecard({"error": 0, "result": []}) == []


def test_racecard_error_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="racecard-api"):
        parse_racecard({"error": 1, "message": "boom"})
    assert any("Racecard feed error: boom" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# Fixture shapes — one file per meeting, three meetings verified.
# --------------------------------------------------------------------------


def test_sa_durbanville_fixture_shape():
    races = parse_racecard(_load_fixture("xdd_2026-10-28.json"), program_name="DURBANVILLE")
    assert len(races) == 8
    assert sum(len(race.runners) for race in races) == 69
    assert all(race.jurisdiction == "SA" for race in races)
    assert all(race.track == "Durbanville" for race in races)


def test_uk_newcastle_fixture_shape():
    races = parse_racecard(_load_fixture("nwc_2026-10-27.json"), program_name="NEWCASTLE_UK")
    assert len(races) == 7
    assert sum(len(race.runners) for race in races) == 45
    assert all(race.jurisdiction == "UK" for race in races)
    assert all(race.track == "Newcastle" for race in races)


def test_uk_catterick_fixture_shape():
    races = parse_racecard(_load_fixture("cjd_2026-10-27.json"), program_name="CATTERICK_UK")
    assert len(races) == 8
    assert sum(len(race.runners) for race in races) == 81
    assert all(race.jurisdiction == "UK" for race in races)
    assert all(race.track == "Catterick" for race in races)


# --------------------------------------------------------------------------
# Race-level mapping — verified tables for the three fixtures.
# --------------------------------------------------------------------------

RACE_ROWS = [
    # SA — Durbanville, XDD, 2026-10-28.
    ("DURBANVILLE", "xdd_2026-10-28.json", 1, "13:07", 1250, 120000.0, 11,
     ["WN", "PL", "DB", "EX", "TF", "P3", "QT", "SW", "BI", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 2, "13:45", 1250, 125000.0, 6,
     ["WN", "PL", "DB", "EX", "TF", "P3", "QT", "SW", "PA", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 3, "14:20", 1600, 100000.0, 8,
     ["WN", "PL", "DB", "EX", "TF", "P3", "QT", "P6", "SW", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 4, "14:55", 1400, 145000.0, 6,
     ["WN", "PL", "DB", "EX", "TF", "P3", "QT", "JP", "SW", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 5, "15:30", 1400, 110000.0, 11,
     ["WN", "PL", "DB", "EX", "TF", "P3", "QT", "JP", "SW", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 6, "16:05", 1600, 120000.0, 7,
     ["WN", "PL", "DB", "EX", "TF", "P3", "QT", "SW", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 7, "16:40", 1600, 90000.0, 9,
     ["WN", "PL", "DB", "EX", "TF", "QT", "SW", "EW"]),
    ("DURBANVILLE", "xdd_2026-10-28.json", 8, "17:15", 1600, 90000.0, 11,
     ["WN", "PL", "EX", "TF", "QT", "SW", "EW"]),
    # UK — Newcastle, NWC, 2026-10-27.
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 1, "14:56", 3400, 231858.0, 6, []),
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 2, "15:25", 4800, 142575.0, 4, []),
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 3, "16:00", 3400, 142575.0, 10, []),
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 4, "16:31", 4800, 271291.0, 4, ["WN", "EX", "TF"]),
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 5, "17:01", 3400, 178519.0, 6,
     ["WN", "PL", "EX", "TF", "SW", "EW"]),
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 6, "17:31", 4000, 206355.0, 6,
     ["WN", "PL", "EX", "TF", "SW", "EW"]),
    ("NEWCASTLE_UK", "nwc_2026-10-27.json", 7, "18:01", 3400, 104344.0, 9,
     ["WN", "PL", "EX", "TF", "SW", "EW"]),
    # UK — Catterick, CJD, 2026-10-27.
    ("CATTERICK_UK", "cjd_2026-10-27.json", 1, "14:40", 1000, 231858.0, 9, []),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 2, "15:10", 1200, 185496.0, 7, []),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 3, "15:40", 1200, 162303.0, 10, []),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 4, "16:10", 1200, 162303.0, 10, []),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 5, "16:40", 1200, 231858.0, 8,
     ["WN", "PL", "EX", "TF", "QT", "JP", "SW", "EW"]),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 6, "17:10", 1400, 185496.0, 15,
     ["WN", "PL", "EX", "TF", "QT", "SW", "EW"]),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 7, "17:40", 3200, 162303.0, 12,
     ["WN", "PL", "EX", "TF", "QT", "SW", "EW"]),
    ("CATTERICK_UK", "cjd_2026-10-27.json", 8, "18:10", 2400, 231858.0, 10,
     ["WN", "PL", "EX", "TF", "QT", "SW", "EW"]),
]


@pytest.mark.parametrize(
    "program_name,fixture,race_number,race_time,distance,prize_money,runner_count,bet_types",
    RACE_ROWS,
    ids=[f"{row[0]}|R{row[2]}" for row in RACE_ROWS],
)
def test_race_maps_from_fixture(
    program_name,
    fixture,
    race_number,
    race_time,
    distance,
    prize_money,
    runner_count,
    bet_types,
):
    races = parse_racecard(_load_fixture(fixture), program_name=program_name)
    race = next(r for r in races if r.race_number == race_number)
    assert race.race_time == race_time
    assert race.distance == distance
    assert race.prize_money == prize_money
    assert len(race.runners) == runner_count
    assert race.bet_types == bet_types


def test_races_filter_returns_single_race():
    races = parse_racecard(_load_fixture("xdd_2026-10-28.json"), races=[2], program_name="DURBANVILLE")
    assert len(races) == 1
    assert races[0].race_number == 2


def test_unknown_race_returns_empty_list():
    races = parse_racecard(_load_fixture("xdd_2026-10-28.json"), races=[99], program_name="DURBANVILLE")
    assert races == []


# --------------------------------------------------------------------------
# Odds — hyphenated fractions incl. numerator < denominator; tote fallback.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "odds,tote_odds,expected",
    [
        ("EVS", None, 2.0),
        ("", "11.00", 11.0),
        (None, "11.00", 11.0),
        ("", "", 0.0),
        ("7-2", None, 4.5),
        ("33-1", None, 34.0),
        ("1-1", None, 2.0),
        ("4-5", None, 1.8),
        ("5-4", None, 2.25),
        ("15-10", None, 2.5),
        ("16-10", None, 2.6),
        ("33-10", None, 4.3),
        ("10-11", None, 1.9091),
    ],
)
def test_to_decimal_handles_fractions_and_fallbacks(odds, tote_odds, expected):
    assert _to_decimal(odds, tote_odds) == expected


def test_all_fixture_runners_have_positive_odds():
    for fixture, program_name in (
        ("xdd_2026-10-28.json", "DURBANVILLE"),
        ("nwc_2026-10-27.json", "NEWCASTLE_UK"),
        ("cjd_2026-10-27.json", "CATTERICK_UK"),
    ):
        races = parse_racecard(_load_fixture(fixture), program_name=program_name)
        runners = _all_runners(races)
        assert runners
        for runner in runners:
            assert runner.odds_decimal > 0


# --------------------------------------------------------------------------
# Barriers — UK NH is None; flat/SA cards are draws.
# --------------------------------------------------------------------------


def test_barriers_follow_source_convention():
    cases = [
    ("xdd_2026-10-28.json", "DURBANVILLE", {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}),
    ("cjd_2026-10-27.json", "CATTERICK_UK", set(range(1, 16))),
    ("nwc_2026-10-27.json", "NEWCASTLE_UK", None),
    ]
    for fixture, program_name, expected in cases:
        races = parse_racecard(_load_fixture(fixture), program_name=program_name)
        barriers = {runner.barrier for race in races for runner in race.runners}
        if expected is None:
            assert all(barrier is None for barrier in barriers)
        else:
            assert barriers == expected


# --------------------------------------------------------------------------
# Runners — values, claims, gear, ratings, odds.
# --------------------------------------------------------------------------


def test_xdd_runner_value_sets():
    runners = _all_runners(
        parse_racecard(_load_fixture("xdd_2026-10-28.json"), program_name="DURBANVILLE")
    )
    assert {runner.gear for runner in runners} == {None, "B", "C"}
    assert {runner.jockey_claim for runner in runners} == {"1.5", "2.5", "4", None}
    assert {runner.sex for runner in runners} == {"Colt", "Filly", "Gelding", "Mare"}
    assert all(runner.owner is not None for runner in runners)


def test_nwc_runner_value_sets():
    runners = _all_runners(
        parse_racecard(_load_fixture("nwc_2026-10-27.json"), program_name="NEWCASTLE_UK")
    )
    assert {runner.gear for runner in runners} == {None, "B", "H", "P", "V"}
    assert {runner.jockey_claim for runner in runners} == {"1.5", "2.5", "3", None}
    assert {runner.sex for runner in runners} == {"Gelding", "Mare"}


def test_cjd_runner_value_sets():
    runners = _all_runners(
        parse_racecard(_load_fixture("cjd_2026-10-27.json"), program_name="CATTERICK_UK")
    )
    assert {runner.gear for runner in runners} == {None, "B", "P", "V"}
    assert {runner.jockey_claim for runner in runners} == {"2.5", None}


@pytest.mark.parametrize(
    "fixture,program_name",
    [
        ("xdd_2026-10-28.json", "DURBANVILLE"),
        ("nwc_2026-10-27.json", "NEWCASTLE_UK"),
        ("cjd_2026-10-27.json", "CATTERICK_UK"),
    ],
)
def test_official_ratings_are_positive_or_absent(fixture, program_name):
    races = parse_racecard(_load_fixture(fixture), program_name=program_name)
    for runner in _all_runners(races):
        assert runner.official_rating is None or runner.official_rating > 0
        assert runner.official_rating != 0


def test_safe_int_treats_sentinels_as_unknown():
    assert _safe_int("--") is None
    assert _safe_int("X") is None
    assert _safe_int("10") == 10


def test_jockey_claim_formats_allowance():
    assert _claim("1.5000") == "1.5"
    assert _claim("2.5000") == "2.5"
    assert _claim("4.0000") == "4"
    assert _claim("0.0000") is None
    assert _claim(None) is None


# --------------------------------------------------------------------------
# Full runner equality — SA and UK first-runner anchors.
# --------------------------------------------------------------------------


def test_xdd_first_runner_full_equality():
    races = parse_racecard(_load_fixture("xdd_2026-10-28.json"), program_name="DURBANVILLE")
    assert races[0].runners[0] == ScrapedRunner(
        horse_name="Stitchintime",
        odds_decimal=4.5,
        odds_fractional="7-2",
        jockey="M Michel",
        trainer="J Crawford",
        barrier=1,
        weight=60.0,
        form=None,
        age=3,
        sex="Gelding",
        gear=None,
        days_since_run=21,
        runner_comments="Fair debut - draw one",
        jockey_claim="1.5",
        official_rating=None,
        pedigree="Vercingetorix - Patchit Up Baby (Ideal World (USA))",
        owner="Messrs W K Graham & R J Munien, Mrs Roberta Jansch & Nick & Val McFall",
        verdict=None,
    )


def test_nwc_first_runner_full_equality():
    races = parse_racecard(_load_fixture("nwc_2026-10-27.json"), program_name="NEWCASTLE_UK")
    assert races[0].runners[0] == ScrapedRunner(
        horse_name="Captain Ted (ire)",
        odds_decimal=34.0,
        odds_fractional="33-1",
        jockey="D Mcmenamin",
        trainer="C Grant",
        barrier=None,
        weight=72.0,
        form=None,
        age=5,
        sex="Gelding",
        gear=None,
        days_since_run=373,
        runner_comments=None,
        jockey_claim=None,
        official_rating=None,
        pedigree="Leading Light (IRE) - Decheekymonkey (IRE) (Presenting (UK))",
        owner="D&D ARMSTRONG LTD",
        verdict=None,
    )


# --------------------------------------------------------------------------
# Synthetic runners — number-name junk and scratch filtering.
# --------------------------------------------------------------------------


def test_synthetic_runner_number_name_filtered():
    assert _map_runner({"Name": "12", "Odds": "5-1"}) is None
    assert _map_runner({"Name": "Real Horse", "Scratched": "1", "Odds": "5-1"}) is None


def test_synthetic_runner_maps_clean_runner():
    runner = _map_runner({"Name": "Real Horse", "Scratched": "0", "Odds": "5-1"})
    assert runner is not None
    assert runner.horse_name == "Real Horse"
    assert runner.odds_decimal == 6.0
    assert runner.odds_fractional == "5-1"


def test_bet_types_are_split_and_uppercased():
    race = _map_race(
        {
            "Race": "3",
            "BetTypes": "wn,pl,db",
            "Runners": [{"Name": "Horse A", "Scratched": "0", "Odds": "5-1"}],
        },
        program_name="DURBANVILLE",
    )
    assert race is not None
    assert race.bet_types == ["WN", "PL", "DB"]

    empty = _map_race(
        {
            "Race": "4",
            "BetTypes": "",
            "Runners": [{"Name": "Horse B", "Scratched": "0", "Odds": "5-1"}],
        },
        program_name="DURBANVILLE",
    )
    assert empty is not None
    assert empty.bet_types == []


# --------------------------------------------------------------------------
# Helpers — jurisdiction, names, times, money, distance.
# --------------------------------------------------------------------------


def test_jurisdiction_mapping():
    assert _jurisdiction("DURBANVILLE") == "SA"
    assert _jurisdiction("NEWCASTLE_UK") == "UK"
    assert _jurisdiction("FAIRVIEW_AUS") == "AUS"
    assert _jurisdiction("BLITZ") == "POOL"
    assert _jurisdiction("X_R1=P1") == "POOL"
    assert _jurisdiction("") is None


def test_is_racecard_program_flags():
    assert is_racecard_program("DURBANVILLE") is True
    assert is_racecard_program("BLITZ") is False
    assert is_racecard_program("") is False


def test_display_name_strips_suffix():
    assert _display_name("NEWCASTLE_UK") == "Newcastle"
    assert _display_name("DURBANVILLE") == "Durbanville"
    assert _display_name("CJD_R7=P2") == "Cjd R7 P2"


def test_race_time_extracts_clock():
    assert _race_time("2026-10-28T13:07:00+02:00") == "13:07"
    assert _race_time("2026-10-28 13:07:00") == "13:07"
    assert _race_time("") == ""


def test_normalise_date_makes_iso_date():
    assert _normalise_date("2026-10-27T00:00:00+02:00") == "2026-10-27"
    assert _normalise_date("2026-10-27 00:00:00") == "2026-10-27"
    assert _normalise_date(None) == date.today().isoformat()


def test_money_strips_currency_and_separators():
    assert _money("R 1 000") == 1000.0
    assert _money("231 858") == 231858.0
    assert _money(None) is None


def test_parse_distance_m():
    assert _parse_distance_m("1250m") == 1250
    assert _parse_distance_m("3400m") == 3400
    assert _parse_distance_m("1000m") == 1000


# --------------------------------------------------------------------------
# Program-level mapping — thin GamePlayRequest option_list entries.
# --------------------------------------------------------------------------


def test_parse_programs_maps_option_list_entries():
    payload = {
        "error": 0,
        "result": {
            "option_list": {
                "1": {
                    "ProgramCode": "XDD",
                    "ProgramName": "DURBANVILLE",
                    "ProgramDate": "2026-10-28T00:00:00+02:00",
                    "Status": "OPEN",
                    "HighestRace": {"0": "8"},
                    "CurrentRace": "1",
                    "MinutesToPost": "900",
                    "AdvertisedStartTime": "2026-10-28 13:07:00",
                    "race_id": "1",
                    "eq_match_id": "1",
                },
                "2": {
                    "ProgramCode": "BLITZ",
                    "ProgramName": "BLITZ",
                    "ProgramDate": "2026-10-27T00:00:00+02:00",
                    "Status": "OPEN",
                    "HighestRace": {"0": "0"},
                    "CurrentRace": None,
                    "MinutesToPost": None,
                    "AdvertisedStartTime": None,
                    "race_id": None,
                    "eq_match_id": None,
                },
            }
        },
    }

    got = parse_programs(payload, target_date="2026-10-28")
    assert len(got) == 1
    program = got[0]
    assert program.program_code == "XDD"
    assert program.program_name == "DURBANVILLE"
    assert program.venue == "Durbanville"
    assert program.jurisdiction == "SA"
    assert program.program_date == "2026-10-28"
    assert program.status == "OPEN"
    assert program.max_race == 8
    assert program.current_race == 1
    assert program.has_racecard is True

    blitz = parse_programs(payload, target_date="2026-10-27")
    assert len(blitz) == 1
    assert blitz[0].program_code == "BLITZ"
    assert blitz[0].jurisdiction == "POOL"
    assert blitz[0].has_racecard is False


def test_parse_programs_reads_the_live_data_option_list():
    """Nov-2026: the live feed moved the option list from ``result`` to
    ``data`` and serves it as a LIST of meeting dicts. A parser that only
    knew the old shape returned zero programs, so every program-code lookup
    (and every live card) was dead."""
    payload = {
        "error": 0,
        "data": {
            "option_list": [
                {
                    "ProgramCode": "XFD",
                    "ProgramName": "TAB Fairview",
                    "ProgramDate": "2026-11-11 00:00:00",
                    "Status": "OPEN",
                    "HighestRace": "8",
                    "CurrentRace": "1",
                },
                {
                    "ProgramCode": "BLITZ",
                    "ProgramName": "BLITZ",
                    "ProgramDate": "2026-11-11 00:00:00",
                    "HighestRace": "0",
                },
            ]
        },
    }

    got = parse_programs(payload)
    assert [p.program_code for p in got] == ["BLITZ", "XFD"]
    fv = next(p for p in got if p.program_code == "XFD")
    assert fv.venue == "Tab Fairview"
    assert fv.jurisdiction == "SA"
    assert fv.program_date == "2026-11-11"
    assert fv.has_racecard is True
    # the pool pseudo-program is still recognised and excluded from cards
    assert next(p for p in got if p.program_code == "BLITZ").has_racecard is False


def test_parse_programs_reads_a_data_option_list_dict():
    """The list form is what the feed serves today; the dict form under
    ``data`` is accepted too, so a reshuffle cannot silently zero it."""
    payload = {
        "error": 0,
        "data": {
            "option_list": {
                "1": {
                    "ProgramCode": "XFD",
                    "ProgramName": "TAB Fairview",
                    "ProgramDate": "2026-11-11",
                }
            }
        },
    }
    got = parse_programs(payload)
    assert [p.program_code for p in got] == ["XFD"]
