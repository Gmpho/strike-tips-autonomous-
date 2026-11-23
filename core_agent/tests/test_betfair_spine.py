"""Betfair SA as the race spine (2026-11-23).

Betway's GetEvent 403s from Modal's Azure IPs emptied the card (14 carry-over
races), while Betfair SA parsed 147 live markets from the same host. The merge
was Betway-first, so that data was discarded. These tests pin the additive
spine: Betfair races Betway could not deliver are added, Betway always owns a
race it already lists, and prices are inherited by horse name.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest

from core_agent.core.adaptive_odds_monitor import _apply_betfair_spine
from core_agent.skills.parsers.betfair_sa import build_card_events


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def _market(
    *,
    course="Pinjarra",
    region="AUS",
    race_name="R4 1200m Mdn",
    race_number=4,
    minutes_ahead=45,
    runners=("Alpha", "Bravo", "Charlie"),
    non_runners=(),
):
    off = datetime.now(timezone.utc) + timedelta(minutes=minutes_ahead)
    return {
        "course": course,
        "region": region,
        "raceName": race_name,
        "raceNumber": race_number,
        "t": off.strftime("%H:%M"),
        "offTime": off.strftime("%H:%M"),
        "offTimeEpochMs": int(off.timestamp() * 1000),
        "runners": [
            {"name": n, **({"non_runner": True} if n in non_runners else {})}
            for n in runners
        ],
    }


def _snapshot(*markets):
    return {"events": {f"1.26586{i}": m for i, m in enumerate(markets)}, "count": len(markets)}


def test_build_card_events_makes_a_real_race():
    snap = _snapshot(_market())
    card = build_card_events(snap)
    assert len(card) == 1
    key = next(iter(card))
    assert key.startswith("bf:")
    ev = card[key]
    assert ev["en"] == "AUS: Pinjarra"
    assert ev["course"] == "Pinjarra"
    assert ev["raceNumber"] == 4
    assert ev["isFinished"] is False
    assert ev["source"] == "betfair"
    assert ev["bf_market_id"] == key.split(":", 1)[1]
    assert [r["name"] for r in ev["runners"]] == ["Alpha", "Bravo", "Charlie"]
    assert all(r["odds"] == "SP" for r in ev["runners"])
    # Off-time is UTC and carries an expiry so readers can drop it.
    parsed = datetime.strptime(ev["t"], "%H:%M").replace(
        year=datetime.now(timezone.utc).year,
        month=datetime.now(timezone.utc).month,
        day=datetime.now(timezone.utc).day,
        tzinfo=timezone.utc,
    )
    assert abs((parsed - datetime.now(timezone.utc)).total_seconds()) < 3 * 3600
    assert ev["expires_at"] > time.time()


def test_harness_markets_are_filtered_out():
    snap = _snapshot(
        _market(race_name="R9 1684m Pace M", race_number=9),
        _market(course="Redcliffe", race_name="R6 1780m Trot", race_number=6),
        _market(course="Vaal", race_name="R2 1400m Mdn", race_number=2),
    )
    card = build_card_events(snap)
    assert len(card) == 1
    assert next(iter(card.values()))["course"] == "Vaal"


def test_finished_market_never_enters_the_spine():
    snap = _snapshot(_market(minutes_ahead=-90))
    assert build_card_events(snap) == {}


def test_scratched_runners_are_not_listed():
    snap = _snapshot(_market(non_runners=("Bravo",)))
    card = build_card_events(snap)
    names = [r["name"] for r in next(iter(card.values()))["runners"]]
    assert names == ["Alpha", "Charlie"]


def _betway_event(course, race_number, t, runners):
    return {
        "en": f"AUS: {course}",
        "course": course,
        "raceNumber": race_number,
        "t": t,
        "runners": runners,
    }


def test_betway_keeps_a_race_it_already_lists():
    spine_t = (datetime.now(timezone.utc) + timedelta(minutes=45)).strftime("%H:%M")
    state = {
        "events": {
            "17512371": _betway_event(
                "Pinjarra", 4, spine_t, [{"name": "Alpha", "odds": 3.5}]
            )
        }
    }
    out = _apply_betfair_spine(state, _snapshot(_market()))
    assert list(out["events"]) == ["17512371"], "Betway's race must not be duplicated"
    assert "spine" not in out


def test_missing_races_are_added_from_betfair():
    state = {"events": {}}
    out = _apply_betfair_spine(state, _snapshot(_market()))
    assert len(out["events"]) == 1
    ev = next(iter(out["events"].values()))
    assert ev["source"] == "betfair"
    assert out["spine"] == {"source": "betfair", "races": 1, "priced": 0}


def test_prices_are_inherited_by_horse_name_across_numbering():
    """Betway numbered the card differently; the horse still gets its price."""
    spine_t = (datetime.now(timezone.utc) + timedelta(minutes=45)).strftime("%H:%M")
    state = {
        "events": {
            "17599999": _betway_event(
                "Pinjarra", 7, "23:59", [{"name": "Alpha", "odds": 2.4}]
            )
        }
    }
    out = _apply_betfair_spine(state, _snapshot(_market()))
    added = [e for e in out["events"].values() if e.get("source") == "betfair"]
    assert len(added) == 1
    odds = {r["name"]: r["odds"] for r in added[0]["runners"]}
    assert odds["Alpha"] == 2.4
    assert odds["Bravo"] == "SP"
    assert out["spine"]["priced"] == 1
    # The spine race keeps its own identity, not Betway's id.
    assert any(k.startswith("bf:") for k in out["events"])


def test_spine_is_idempotent():
    state = {"events": {}}
    first = _apply_betfair_spine(state, _snapshot(_market()))
    count = len(first["events"])
    second = _apply_betfair_spine(first, _snapshot(_market()))
    assert len(second["events"]) == count


def test_empty_betfair_snapshot_leaves_the_card_untouched():
    state = {
        "events": {
            "1": _betway_event("Vaal", 3, "14:00", [{"name": "X", "odds": 2}])
        }
    }
    out = _apply_betfair_spine(state, {"events": {}, "count": 0})
    assert list(out["events"]) == ["1"]
    assert "spine" not in out
