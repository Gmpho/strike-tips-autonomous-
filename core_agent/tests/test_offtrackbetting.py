"""Offtrackbetting.com results parser — the fallback when ATR is quiet.

Nov-2026: ZERO Hong Kong races had ever been captured by ATR, so every HK
league pick hung until it expired, and four UK/IRE races never appeared at
all. Offtrackbetting serves the same cards from a plain JSON endpoint; these
tests pin the mapping (positions, unplaced runners, scratches, prices) and
the TTL/backoff behaviour so a failing endpoint is not hammered.
"""
import json
import os

import pytest

from core_agent.skills.parsers import offtrackbetting as otb


def _payload():
    """One finished race plus the runners who did not place."""
    return {
        "events": [
            {
                "eventNo": {"$numberDouble": "1"},
                "postTime": "2026-11-11 12:15:00",
                "distance": "1200",
                "conditions": "Handicap",
                "runners": [{"programNumber": "5"}],
                "results": {
                    "finisher": [
                        {"runnerName": "Lovely Miles", "finishPosition": {"$numberDouble": "1"},
                         "winAmount": "21.80", "placeAmount": "6.60", "programNumber": "5"},
                        {"runnerName": "Fortune Kingo", "finishPosition": {"$numberDouble": "2"},
                         "placeAmount": "3.40", "programNumber": "6"},
                        {"runnerName": "Only U", "finishPosition": {"$numberDouble": "3"},
                         "placeAmount": "5.40", "programNumber": "11"},
                        {"runnerName": "Cyber Hero", "finishPosition": {"$numberDouble": "4"},
                         "placeAmount": "8.10", "programNumber": "9"},
                    ],
                    "alsoRan": ["Circuit Century", "Amo Ergo Sum"],
                    "scratches": ["Among The Willows"],
                    "dividends": {"POOL": {"JP": "1000"}},
                },
            },
            {
                # A race that has not run yet: no results at all.
                "eventNo": {"$numberDouble": "2"},
                "postTime": "2026-11-11 12:50:00",
                "runners": [{"programNumber": "1"}],
                "results": {},
            },
        ]
    }


def test_num_reads_mongo_extended_json():
    assert otb._num({"$numberDouble": "1"}) == 1.0
    assert otb._num({"$numberInt": "7"}) == 7.0
    assert otb._num("21.80") == 21.8
    assert otb._num(None) is None
    assert otb._num({"other": 1}) is None


def test_parse_meeting_maps_finishers_placers_and_scratches():
    races = otb._parse_meeting(_payload(), "2026-11-11")
    # The race that has not run is never a result.
    assert len(races) == 1
    race = races[0]
    assert race["race_number"] == "1"
    assert race["off_time"] == "12:15"
    names = {r["name"]: r for r in race["runners"]}

    assert names["Lovely Miles"]["position"] == 1
    assert names["Lovely Miles"]["odds_decimal"] == 21.8
    assert names["Fortune Kingo"]["position"] == 2
    assert names["Cyber Hero"]["position"] == 4

    # Ran but did not place: on the card, no position, not a non-runner.
    assert names["Circuit Century"]["position"] is None
    assert names["Circuit Century"]["non_runner"] is False

    # Scratched: never ran, so the pick is refunded rather than lost.
    assert names["Among The Willows"]["non_runner"] is True


def test_parse_meeting_returns_nothing_without_a_finished_race():
    assert otb._parse_meeting({"events": [{"eventNo": 1, "results": {}}]}, "2026-11-11") == []
    assert otb._parse_meeting({}, "2026-11-11") == []
    assert otb._parse_meeting({"events": "nonsense"}, "2026-11-11") == []


def test_course_id_matches_by_base_name(monkeypatch):
    courses = [
        {"id": 451, "name": "Happy Valley (Hong Kong)", "base": "happy valley", "country": "hong kong"},
        {"id": 446, "name": "Fairview (SAF)", "base": "fairview", "country": "saf"},
        {"id": 300, "name": "Aintree (UK)", "base": "aintree", "country": "uk"},
    ]
    monkeypatch.setattr(otb, "course_index", lambda refresh=False: courses)
    assert otb.course_id_for("Happy Valley") == 451
    assert otb.course_id_for("fairview") == 446
    assert otb.course_id_for("Aintree") == 300
    assert otb.course_id_for("Nowhere Racecourse") is None
    assert otb.course_id_for("") is None


def test_fetch_meeting_caches_a_finished_card(tmp_path, monkeypatch):
    """A finished card is immutable: the second call must not re-fetch."""
    monkeypatch.setattr(otb, "_data_dir", lambda: str(tmp_path))
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return _payload()

    monkeypatch.setattr(otb, "_fetch_json", fake_fetch)
    first = otb.fetch_meeting(451, "2026-11-10")
    second = otb.fetch_meeting(451, "2026-11-10")
    assert len(first) == 1 and len(second) == 1
    assert len(calls) == 1  # served from the cache


def test_fetch_meeting_remembers_a_failure(tmp_path, monkeypatch):
    """A failing endpoint must not be retried every cycle."""
    monkeypatch.setattr(otb, "_data_dir", lambda: str(tmp_path))
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return None

    monkeypatch.setattr(otb, "_fetch_json", fake_fetch)
    assert otb.fetch_meeting(451, "2026-11-10") == []
    after_first = len(calls)
    assert after_first >= 1
    assert otb.fetch_meeting(451, "2026-11-10") == []
    assert len(calls) == after_first  # the retry window swallowed the second attempt


def test_fetch_meeting_rejects_a_bad_date(tmp_path, monkeypatch):
    monkeypatch.setattr(otb, "_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(otb, "_fetch_json", lambda url: (_ for _ in ()).throw(AssertionError("no fetch")))
    assert otb.fetch_meeting(451, "not-a-date") == []
    assert otb.fetch_meeting(0, "2026-11-10") == []
