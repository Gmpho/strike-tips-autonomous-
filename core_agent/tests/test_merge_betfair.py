"""Unit tests for the Betfair SA form-data merge (_merge_bf_into)."""
import pytest

from core_agent.core.adaptive_odds_monitor import _merge_bf_into


def _bw_event(course, time, runners):
    return {
        "course": course,
        "t": time,
        "runners": [{"name": n} for n in runners],
    }


def _bf_event(course, time, runners_with_meta):
    return {
        "course": course,
        "t": time,
        "runners": [
            {"name": n, "gear": g, "daysSinceRun": d}
            for (n, g, d) in runners_with_meta
        ],
    }


# ---------------------------------------------------------------------------
# Exact match
# ---------------------------------------------------------------------------
def test_exact_match_attaches_gear_and_days():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07",
                           ["Task Force", "Diaval", "Eye On The Victory"])
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("scottsville", "12:07", [
                ("Task Force", "Blinkers · Tongue strap", 16),
                ("Diaval", None, 21),
                ("Eye On The Victory", None, None),
            ])
        }
    }
    _merge_bf_into(state, bf)
    r = state["events"]["1"]["runners"]
    assert r[0]["gear"] == "Blinkers · Tongue strap"
    assert r[0]["daysSinceRun"] == 16
    # gear absent on source -> key omitted on Betway (additive only)
    assert "gear" not in r[1]
    assert r[1]["daysSinceRun"] == 21
    # both absent on source -> neither key present
    assert "gear" not in r[2] and "daysSinceRun" not in r[2]


# ---------------------------------------------------------------------------
# Fuzzy match (cross-spelling)
# ---------------------------------------------------------------------------
def test_fuzzy_match_handles_spacing_and_case():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07", ["Night Fever"])
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "12:07", [
                ("Night  Fever (IRE)", "Hood · Blinkers", 14),
            ])
        }
    }
    _merge_bf_into(state, bf)
    assert state["events"]["1"]["runners"][0]["gear"] == "Hood · Blinkers"
    assert state["events"]["1"]["runners"][0]["daysSinceRun"] == 14


# ---------------------------------------------------------------------------
# No match (below 0.6 similarity) -> runner stays clean
# ---------------------------------------------------------------------------
def test_no_match_leaves_runner_clean():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07",
                           ["Totally Different Horse"])
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "12:07", [
                ("Some Other Name", "Blinkers", 7),
            ])
        }
    }
    _merge_bf_into(state, bf)
    r = state["events"]["1"]["runners"][0]
    assert "gear" not in r
    assert "daysSinceRun" not in r


# ---------------------------------------------------------------------------
# Course/time mismatch -> merge is a no-op
# ---------------------------------------------------------------------------
def test_different_course_or_time_skipped():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07", ["Horse X"]),
            "2": _bw_event("Turffontein", "14:00", ["Horse Y"]),
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "13:00", [("Horse X", "Hood", 5)]),  # wrong time
            "mk2": _bf_event("Durbanville", "12:07", [("Horse Y", "Hood", 5)]),  # wrong course
        }
    }
    _merge_bf_into(state, bf)
    assert "gear" not in state["events"]["1"]["runners"][0]
    assert "gear" not in state["events"]["2"]["runners"][0]


# ---------------------------------------------------------------------------
# One-to-one: two SA horses with similar names must not swap
# ---------------------------------------------------------------------------
def test_one_to_one_match_prevents_swap():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07",
                           ["Silver Storm", "Storm Chaser"])
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "12:07", [
                ("Silver Storm", "Blinkers", 5),
                ("Storm Chaser", "Hood", 7),
            ])
        }
    }
    _merge_bf_into(state, bf)
    runners = {r["name"]: r for r in state["events"]["1"]["runners"]}
    assert runners["Silver Storm"]["gear"] == "Blinkers"
    assert runners["Silver Storm"]["daysSinceRun"] == 5
    assert runners["Storm Chaser"]["gear"] == "Hood"
    assert runners["Storm Chaser"]["daysSinceRun"] == 7


# ---------------------------------------------------------------------------
# Partial coverage: some races covered, some not
# ---------------------------------------------------------------------------
def test_partial_coverage_only_attaches_covered_races():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07", ["Horse A"]),
            "2": _bw_event("Durbanville", "13:00", ["Horse B"]),
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "12:07", [("Horse A", "Hood", 3)]),
        }
    }
    _merge_bf_into(state, bf)
    assert state["events"]["1"]["runners"][0]["gear"] == "Hood"
    assert "gear" not in state["events"]["2"]["runners"][0]


# ---------------------------------------------------------------------------
# Additive only: never overwrite existing snapshot fields
# ---------------------------------------------------------------------------
def test_existing_fields_not_overwritten():
    state = {
        "events": {
            "1": {
                "course": "Scottsville",
                "t": "12:07",
                "runners": [
                    {"name": "Horse A", "gear": "FROM_BETWAY", "odds": 3.0}
                ],
            }
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "12:07", [
                ("Horse A", "Hood", 5),
            ])
        }
    }
    _merge_bf_into(state, bf)
    r = state["events"]["1"]["runners"][0]
    assert r["gear"] == "FROM_BETWAY"  # not overwritten
    assert r["daysSinceRun"] == 5     # new key added
    assert r["odds"] == 3.0          # untouched


# ---------------------------------------------------------------------------
# Degradation: empty / malformed snapshots don't break anything
# ---------------------------------------------------------------------------
def test_empty_snapshot_is_noop():
    state = {
        "events": {
            "1": _bw_event("Scottsville", "12:07", ["Horse A"]),
        }
    }
    _merge_bf_into(state, {"events": {}, "count": 0})
    assert "gear" not in state["events"]["1"]["runners"][0]


def test_malformed_snapshot_does_not_raise():
    state = {"events": {"1": _bw_event("Scottsville", "12:07", ["Horse A"])}}
    # No bf_events at all
    _merge_bf_into(state, {"count": 0})
    # Garbage bf_events
    _merge_bf_into(state, {"events": {"x": "not-a-dict"}})
    # None entirely
    _merge_bf_into(state, None)
    assert "gear" not in state["events"]["1"]["runners"][0]


# ---------------------------------------------------------------------------
# Existing Betway fields stay byte-identical
# ---------------------------------------------------------------------------
def test_existing_betway_fields_preserved():
    state = {
        "events": {
            "1": {
                "course": "Scottsville",
                "t": "12:07",
                "en": "South Africa: Scottsville",
                "isFinished": False,
                "raceNumber": 1,
                "runners": [
                    {"name": "Horse A", "odds": 4.5, "outcomeName": "Horse A"}
                ],
            }
        }
    }
    bf = {
        "events": {
            "mk1": _bf_event("Scottsville", "12:07", [
                ("Horse A", "Hood", 5),
            ])
        }
    }
    pre_snapshot_keys = sorted(state["events"]["1"]["runners"][0].keys())
    _merge_bf_into(state, bf)
    post_runner = state["events"]["1"]["runners"][0]
    # Original keys untouched
    for k in pre_snapshot_keys:
        assert k in post_runner
    # New keys added
    assert "gear" in post_runner
    assert "daysSinceRun" in post_runner
    # Existing values preserved
    assert post_runner["odds"] == 4.5
    assert post_runner["outcomeName"] == "Horse A"
    assert state["events"]["1"]["en"] == "South Africa: Scottsville"
    assert state["events"]["1"]["isFinished"] is False
    assert state["events"]["1"]["raceNumber"] == 1
