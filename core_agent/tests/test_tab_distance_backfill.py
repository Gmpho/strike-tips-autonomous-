"""Real race distances from TAB's live card (Nov-2026).

Betway's card states no distance and the merged market snapshot carried
``distance_m`` for NONE of the SA meetings, so every exotic leg rendered
"· —" on the board. TAB's live feed states the distance for every race of a
meeting, and one plain-JSON call per meeting fills the gap.

This file pins the lookup and its day guard: a distance belonging to another
meeting's card must never be applied to this one.
"""

import asyncio
from datetime import date

from core_agent.core.strike_tips import (
    _finalise_exotic_plays,
    _norm_text,
    _tab_card_distances,
)


class _Program:
    def __init__(self, code, name, date_iso, jurisdiction="SA", has_racecard=True):
        self.program_code = code
        self.program_name = name
        self.venue = name.replace("TAB ", "").title()
        self.jurisdiction = jurisdiction
        self.program_date = date_iso
        self.has_racecard = has_racecard


class _Race:
    def __init__(self, race_number, distance):
        self.race_number = race_number
        self.distance = distance


def _patch_tab(monkeypatch, programs, card_races):
    """Point the helper at a fake live feed."""
    import core_agent.core.strike_tips as st

    async def fake_programs(ttl_secs=900):
        return programs

    async def fake_racecard(code, program_date=None, program_name=None, races=None):
        return card_races

    monkeypatch.setattr(st, "_tab_programs", fake_programs)
    monkeypatch.setattr(
        "core_agent.skills.parsers.racecard_api.get_racecard", fake_racecard
    )


def test_tab_card_distances_map_race_numbers(monkeypatch):
    day = date.today().isoformat()
    _patch_tab(
        monkeypatch,
        [_Program("XFD", "TAB Fairview", day)],
        [_Race(1, 1200), _Race(2, 1400), _Race(3, None), _Race(4, 0)],
    )
    got = asyncio.run(_tab_card_distances("Fairview", day))
    # only real distances — a race TAB does not state stays unknown
    assert got == {1: 1200, 2: 1400}

def test_tab_card_distances_refuse_another_day(monkeypatch):
    """A card from a different meeting must never be applied to this one."""
    day = date.today().isoformat()
    _patch_tab(
        monkeypatch,
        [_Program("XFD", "TAB Fairview", "2026-01-01")],
        [_Race(1, 1200)],
    )
    assert asyncio.run(_tab_card_distances("Fairview", day)) == {}


def test_tab_card_distances_ignore_an_unknown_track(monkeypatch):
    day = date.today().isoformat()
    _patch_tab(
        monkeypatch,
        [_Program("XFD", "TAB Fairview", day)],
        [_Race(1, 1200)],
    )
    assert asyncio.run(_tab_card_distances("Kenilworth", day)) == {}


def test_tab_card_distances_skip_pool_pseudo_programs(monkeypatch):
    """A pool pseudo-program has no card, so it can state no distance."""
    day = date.today().isoformat()
    _patch_tab(
        monkeypatch,
        [_Program("BLITZ", "BLITZ", day, jurisdiction="POOL", has_racecard=False)],
        [_Race(1, 1200)],
    )
    assert asyncio.run(_tab_card_distances("Blitz", day)) == {}


def _play(track="Fairview", legs=((1, "ROYAL FLUSH"), (2, "SILVER ARROW"))):
    return {
        "_track": track,
        "jurisdiction": "SA",
        "pool": "BIPOT",
        "legs": [r for r, _ in legs],
        "combinations": [
            {"race": race, "banker": name, "savers": []} for race, name in legs
        ],
        "estimated_combinations": 1,
    }


def _snapshot(track="Fairview", names=("ROYAL FLUSH", "SILVER ARROW")):
    return {_norm_text(track): {_norm_text(n) for n in names}}


def test_finalise_fills_distance_for_string_leg_numbers():
    """The AI often returns a leg number as a string; the leg then kept "· —"
    because the card's int never matched."""
    play = _play(legs=(("1", "ROYAL FLUSH"), ("2", "SILVER ARROW")))
    all_results = {
        "Fairview": [
            {"race_number": 1, "distance": 1200},
            {"race_number": 2, "distance": 1400},
        ]
    }
    out = _finalise_exotic_plays([play], all_results, _snapshot(), {}, {})
    distances = {c["race"]: c.get("distance_m") for c in out[0]["combinations"]}
    assert distances == {"1": 1200, "2": 1400}


def test_finalise_keeps_an_unknown_distance_unknown():
    """A race the card does not cover must stay blank, never a placeholder."""
    play = _play(legs=((1, "ROYAL FLUSH"), (2, "SILVER ARROW")))
    all_results = {"Fairview": [{"race_number": 1, "distance": 1200}]}
    out = _finalise_exotic_plays([play], all_results, _snapshot(), {}, {})
    distances = {c["race"]: c.get("distance_m") for c in out[0]["combinations"]}
    assert distances == {1: 1200, 2: None}
