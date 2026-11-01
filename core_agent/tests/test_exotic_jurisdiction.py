"""Exotic play jurisdiction tagging and the guards that gate them.

Oct-2026: international (UK/IRE) exotics were added to the region scan. The
Betway snapshot is South-Africa-only, so the phantom-meeting guard must not
read "no snapshot coverage" as "phantom meeting" for a non-SA card — it would
silently delete every international ticket. This file pins that split so a
future refactor cannot quietly re-break it.
"""

import pytest

from core_agent.core.strike_tips import (
    _finalise_exotic_plays,
    _norm_text,
    _play_matches_snapshot,
)


def _play(track="Durbanville", jurisdiction="SA", pool="BIPOT", legs=(1, 2, 3, 4, 5, 6)):
    return {
        "_track": track,
        "jurisdiction": jurisdiction,
        "pool": pool,
        "legs": list(legs),
        "combinations": [
            {"race": 1, "banker": "ROYAL FLUSH", "savers": []},
            {"race": 2, "banker": "SILVER ARROW", "savers": []},
        ],
        "estimated_combinations": 1,
    }


def _snapshot(track="Durbanville", names=("ROYAL FLUSH", "SILVER ARROW")):
    return {_norm_text(track): {_norm_text(n) for n in names}}


def test_sa_play_needs_snapshot_coverage():
    play = _play()
    assert _play_matches_snapshot(play, _snapshot()) is True
    # Same card, no snapshot entry: phantom-meeting protection stands.
    assert _play_matches_snapshot(play, _snapshot(track="Kenilworth")) is False


def test_non_sa_play_survives_absent_snapshot():
    # Betway never lists Catterick, so coverage cannot exist. The region scan
    # already proved the card's date from the TAB manifest filename.
    play = _play(track="Catterick", jurisdiction="UK", pool="JACKPOT", legs=(1, 2, 3, 4))
    assert _play_matches_snapshot(play, _snapshot()) is True
    assert _play_matches_snapshot(play, {}) is True


def test_play_without_jurisdiction_defaults_to_sa():
    play = _play()
    play.pop("jurisdiction")
    assert _play_matches_snapshot(play, _snapshot()) is True
    out = _finalise_exotic_plays([play], {}, _snapshot(), {}, {})
    assert out[0]["jurisdiction"] == "SA"


def test_finalise_stamps_jurisdiction_and_fills_dividend():
    sa = _play()
    uk = _play(track="Catterick", jurisdiction="UK", pool="JACKPOT", legs=(1, 2, 3, 4))
    out = _finalise_exotic_plays([sa, uk], {}, _snapshot(), {}, {})
    assert len(out) == 2
    assert {p["jurisdiction"] for p in out} == {"SA", "UK"}
    by_track = {p["_track"]: p for p in out}
    # 450.0 per leg is the documented deterministic estimate.
    assert by_track["Durbanville"]["estimated_dividend"] == 450.0 * 6
    assert by_track["Catterick"]["estimated_dividend"] == 450.0 * 4


def test_finalise_keeps_supplied_dividend():
    play = _play()
    play["estimated_dividend"] = 1234.5
    out = _finalise_exotic_plays([play], {}, _snapshot(), {}, {})
    assert out[0]["estimated_dividend"] == 1234.5


def test_finalise_backfills_distance_from_race_card():
    play = _play()
    all_results = {
        "Durbanville": [
            {"race_number": 1, "distance": 1250},
            {"race_number": 2, "distance": 1600},
        ]
    }
    out = _finalise_exotic_plays([play], all_results, _snapshot(), {}, {})
    distances = {c["race"]: c.get("distance_m") for c in out[0]["combinations"]}
    assert distances == {1: 1250, 2: 1600}


def test_finalise_drops_cloth_number_tickets():
    play = _play()
    play["combinations"] = [{"race": 1, "banker": "3", "savers": []}]
    out = _finalise_exotic_plays([play], {}, _snapshot(), {}, {})
    assert out == []
