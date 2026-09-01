"""Tests for Betfair enriched form fields (all regions, 12 fields)."""
import sys
from unittest.mock import MagicMock

# Mock polars if not installed (CI without heavy deps)
if "polars" not in sys.modules:
    sys.modules["polars"] = MagicMock()
for _m in ["fitz", "bs4", "PyMuPDF", "reportlab", "chromadb", "honcho"]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

import pytest

from core_agent.skills.parsers.betfair_sa import (
    BetfairSA,
    _COUNTRY_FILTER,
    _clean_str,
    _parse_int_field,
)
from core_agent.core.adaptive_odds_monitor import _merge_bf_into
from core_agent.skills.parsers.tab4racing import ScrapedRunner
from core_agent.skills.race_analysis.analyzer import Runner
from core_agent.services.racing_service import RacingService
from core_agent.skills.parsers.tab4racing import ScrapedRace


# ---------------------------------------------------------------------------
# Country filter: now all regions
# ---------------------------------------------------------------------------
def test_country_filter_is_none():
    assert _COUNTRY_FILTER is None
    # BetfairSA defaults to None -> no filtering
    api = BetfairSA()
    assert api.country_filter is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  hello ", "hello"),
        ("", None),
        ("   ", None),
        (None, None),
        (123, None),
        ("Runner Comments: good", "Runner Comments: good"),
    ],
)
def test_clean_str(raw, expected):
    assert _clean_str(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("95", 95),
        ("  100 ", 100),
        (0, 0),
        ("abc", None),
        (None, None),
        ("", None),
        (3.0, 3),
    ],
)
def test_parse_int_field(raw, expected):
    assert _parse_int_field(raw) == expected


# ---------------------------------------------------------------------------
# ScrapedRunner dataclass has new fields
# ---------------------------------------------------------------------------
def test_scraped_runner_has_enriched_fields():
    r = ScrapedRunner(
        horse_name="Test",
        odds_decimal=5.0,
        gear="Blinkers",
        days_since_run=14,
        runner_comments="Needs soft",
        jockey_claim="3",
        official_rating=95,
        pedigree="Sire x Dam",
        owner="Owner Ltd",
        verdict="Should go well",
    )
    assert r.gear == "Blinkers"
    assert r.days_since_run == 14
    assert r.official_rating == 95
    assert r.pedigree == "Sire x Dam"


# ---------------------------------------------------------------------------
# Runner dataclass has new fields
# ---------------------------------------------------------------------------
def test_runner_has_enriched_fields():
    r = Runner(
        horse_name="Test",
        odds_decimal=5.0,
        gear="Hood",
        days_since_run=21,
        official_rating=88,
        pedigree="A x B",
        owner="Owner",
        verdict="Each-way chance",
    )
    assert r.gear == "Hood"
    assert r.official_rating == 88


# ---------------------------------------------------------------------------
# _parse_market enriched
# ---------------------------------------------------------------------------
def _runner_with_meta(name, meta, top=None):
    d = {"runnername": name, "metadata": meta}
    if top:
        d.update(top)
    return d


def test_parse_market_enriched_all_fields():
    api = BetfairSA()
    data = {
        "runners": [
            _runner_with_meta(
                "Task Force",
                {
                    "wearing": "blinkers and tongue strap",
                    "days_since_last_run": "16",
                    "runner_comments": "Ran well last time",
                    "jockey_claim": "1.5",
                    "official_rating": "95",
                    "pedigree": "Gimmethegreenlight x Dam",
                    "owner": "Mr Smith",
                    "verdict": "Leading contender",
                    "trainer": "J Snaith",
                    "age": "4",
                    "weight": "60.5",
                    "form": "123-1",
                },
            ),
            _runner_with_meta("Diaval", {"wearing": None, "days_since_last_run": None}),
        ],
        "event": {"name": "Kenilworth", "startTime": 1788084420000},
        "markets": [{"name": "R1 1200m Mdn"}],
    }
    ev = api._parse_market("1.261657897", data)
    assert ev is not None
    runners = {r["name"]: r for r in ev["runners"]}
    tf = runners["Task Force"]
    assert tf["gear"] == "Blinkers · Tongue strap"
    assert tf["daysSinceRun"] == 16
    assert tf["runner_comments"] == "Ran well last time"
    assert tf["jockey_claim"] == "1.5"
    assert tf["official_rating"] == 95
    assert tf["pedigree"] == "Gimmethegreenlight x Dam"
    assert tf["owner"] == "Mr Smith"
    assert tf["verdict"] == "Leading contender"
    assert tf["trainer"] == "J Snaith"
    assert tf["age"] == 4
    assert tf["weight"] == "60.5"
    assert tf["form"] == "123-1"
    # absent fields -> key omitted
    diaval = runners["Diaval"]
    assert "gear" not in diaval
    assert "runner_comments" not in diaval


def test_parse_market_fallback_to_top_level():
    """When metadata missing, top-level fields are used."""
    api = BetfairSA()
    data = {
        "runners": [
            {"runnername": "Horse A", "metadata": {}, "wearing": "Hood", "official_rating": "88", "owner": "Top Owner"}
        ],
        "event": {"name": "Turffontein", "startTime": 1788084420000},
        "markets": [{"name": "R1"}],
    }
    ev = api._parse_market("1.1", data)
    r = ev["runners"][0]
    assert r["gear"] == "Hood"
    assert r["official_rating"] == 88
    assert r["owner"] == "Top Owner"


# ---------------------------------------------------------------------------
# _merge_bf_into with all new fields
# ---------------------------------------------------------------------------
def _bw_event(course, time, runners):
    return {"course": course, "t": time, "runners": [{"name": n} for n in runners]}


def _bf_event(course, time, runners):
    # runners: list of dicts with enriched keys
    return {"course": course, "t": time, "runners": runners}


def test_merge_enriched_fields_attached():
    state = {"events": {"1": _bw_event("Kenilworth", "12:07", ["Task Force"])}}
    bf = {
        "events": {
            "mk1": _bf_event(
                "kenilworth",
                "12:07",
                [
                    {
                        "name": "Task Force",
                        "gear": "Blinkers",
                        "daysSinceRun": 16,
                        "runner_comments": "Needs further",
                        "official_rating": 95,
                        "pedigree": "Sire x Dam",
                        "owner": "Owner Ltd",
                        "verdict": "Place chance",
                        "trainer": "J Snaith",
                        "age": 4,
                        "weight": "60",
                        "form": "1-2-3",
                        "jockey_claim": "2.5",
                    }
                ],
            )
        }
    }
    _merge_bf_into(state, bf)
    r = state["events"]["1"]["runners"][0]
    assert r["gear"] == "Blinkers"
    assert r["daysSinceRun"] == 16
    assert r["runner_comments"] == "Needs further"
    assert r["official_rating"] == 95
    assert r["pedigree"] == "Sire x Dam"
    assert r["owner"] == "Owner Ltd"
    assert r["verdict"] == "Place chance"
    assert r["trainer"] == "J Snaith"
    assert r["age"] == 4
    assert r["weight"] == "60"
    assert r["form"] == "1-2-3"
    assert r["jockey_claim"] == "2.5"


def test_merge_does_not_overwrite_existing():
    state = {
        "events": {
            "1": {
                "course": "Kenilworth",
                "t": "12:07",
                "runners": [{"name": "Horse A", "gear": "FROM_BETWAY", "owner": "Original"}],
            }
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event(
                "Kenilworth",
                "12:07",
                [{"name": "Horse A", "gear": "Hood", "owner": "New Owner", "verdict": "New"}],
            )
        }
    }
    _merge_bf_into(state, bf)
    r = state["events"]["1"]["runners"][0]
    assert r["gear"] == "FROM_BETWAY"  # not overwritten
    assert r["owner"] == "Original"  # not overwritten
    assert r["verdict"] == "New"  # new key added


def test_merge_with_non_sa_tracks():
    """With _COUNTRY_FILTER=None, non-SA tracks are handled the same."""
    state = {"events": {"1": _bw_event("Ascot", "14:00", ["Horse UK"])}}
    bf = {
        "events": {
            "mk1": _bf_event("Ascot", "14:00", [{"name": "Horse UK", "gear": "Visor", "daysSinceRun": 10}])
        }
    }
    _merge_bf_into(state, bf)
    assert state["events"]["1"]["runners"][0]["gear"] == "Visor"


# ---------------------------------------------------------------------------
# RacingService passthrough
# ---------------------------------------------------------------------------
def test_racing_service_passthrough_enriched():
    sr = ScrapedRunner(
        horse_name="Enriched Horse",
        odds_decimal=4.5,
        jockey="Jockey A",
        trainer="Trainer A",
        gear="Blinkers",
        days_since_run=10,
        runner_comments="Good run",
        official_rating=90,
        pedigree="Sire x Dam",
        owner="Owner X",
        verdict="Chance",
        jockey_claim="1",
    )
    race = ScrapedRace(
        track="Kenilworth",
        race_number=1,
        race_time="12:07",
        distance=1600,
        track_condition="Good",
        runners=[sr],
    )
    svc = RacingService()
    race_card, _, _ = svc._convert_race_data(race)
    assert len(race_card.runners) == 1
    r = race_card.runners[0]
    assert r.gear == "Blinkers"
    assert r.days_since_run == 10
    assert r.runner_comments == "Good run"
    assert r.official_rating == 90
    assert r.pedigree == "Sire x Dam"
    assert r.owner == "Owner X"
    assert r.verdict == "Chance"
    assert r.jockey_claim == "1"
