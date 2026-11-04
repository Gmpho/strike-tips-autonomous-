"""Distances must be real or unknown — never a 1600m placeholder.

Sep-2026: every leg of the Greyville card showed 1600m because the Betway
parser hardcoded distance=1600 while the snapshot already carried
distance_m, and the PDF mapper did the same.
"""
from core_agent.skills.parsers.betway_api import BetwayAPI
from core_agent.skills.parsers.tab_pdf_mapper import _map_pdf_to_races


def _snapshot(*events):
    return {"events": {f"e{i}": e for i, e in enumerate(events)}}


def _event(**kw):
    base = {
        "en": "South Africa: Greyville",
        "raceNumber": 1,
        "t": "12:00",
        "runners": [
            {"outcomeName": "H1", "odds": 2.0, "jockeyName": "J",
             "trainerName": "T", "draw": 1, "form": "1"},
        ],
    }
    base.update(kw)
    return base


def test_betway_uses_snapshot_distance_m():
    api = BetwayAPI.__new__(BetwayAPI)
    races = api._parse_snapshot(_snapshot(_event(distance_m=1200)))
    assert races[0].distance == 1200


def test_betway_parses_distance_from_name():
    api = BetwayAPI.__new__(BetwayAPI)
    races = api._parse_snapshot(_snapshot(_event(name="R2 1400m Maiden Plate")))
    assert races[0].distance == 1400


def test_betway_unknown_distance_is_none_not_1600():
    api = BetwayAPI.__new__(BetwayAPI)
    races = api._parse_snapshot(_snapshot(_event()))
    assert races[0].distance is None


def test_pdf_mapper_uses_harvested_distance():
    intelligence = {
        "parsed_tips": [{"race_number": 1, "selections": "H1"}],
        "races": {1: {"distance_m": 1000, "surface": "Turf"}},
    }
    races = _map_pdf_to_races(intelligence, "greyville")
    assert races[0].distance == 1000


def test_pdf_mapper_unknown_distance_is_none_not_1600():
    intelligence = {"parsed_tips": [{"race_number": 1, "selections": "H1"}]}
    races = _map_pdf_to_races(intelligence, "greyville")
    assert races[0].distance is None
