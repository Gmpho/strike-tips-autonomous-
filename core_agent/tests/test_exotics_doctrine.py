"""Exotics textbook doctrine: widen-the-murk, flagged auto-qualify,
single-race suitability gate, OKF bundle presence.

Pure functions — no I/O, no creds.
"""
import pytest

from core_agent.skills.exotics.builder import (
    leg_uncertainty,
    widen_murkiest_legs,
    apply_flagged_horses,
    race_suitability,
)


def _runners(probs):
    return [{"name": f"H{i}", "prob": p} for i, p in enumerate(probs)]


def test_uncertainty_standout_vs_chaos():
    standout = leg_uncertainty(_runners([0.5, 0.2, 0.1, 0.05]))
    chaos = leg_uncertainty(_runners([0.2, 0.19, 0.18, 0.17, 0.15] + [0.02] * 11))
    assert standout < chaos
    assert leg_uncertainty([]) == 0.0


def test_widen_hits_murkiest_only():
    race_map = {
        5: {"runners": _runners([0.5, 0.2, 0.1, 0.05])},          # standout
        6: {"runners": _runners([0.2, 0.19, 0.18, 0.1, 0.1])},    # murk
    }
    legs = [
        {"race": 5, "banker": {"name": "H0"}, "savers": [{"name": "H1"}, {"name": "H2"}]},
        {"race": 6, "banker": {"name": "H0"}, "savers": [{"name": "H1"}, {"name": "H2"}]},
    ]
    out = widen_murkiest_legs(legs, race_map, budget=1)
    by_race = {l["race"]: l for l in out}
    assert len(by_race[6]["savers"]) == 3
    assert by_race[6].get("widened") is True
    assert len(by_race[5]["savers"]) == 2  # standout untouched
    # input not mutated
    assert len(legs[1]["savers"]) == 2


def test_widen_zero_budget_noop():
    race_map = {5: {"runners": _runners([0.2, 0.19, 0.18])}}
    legs = [{"race": 5, "banker": {"name": "H0"}, "savers": [{"name": "H1"}]}]
    assert widen_murkiest_legs(legs, race_map, budget=0) == legs


def test_flagged_displaces_weakest_saver():
    legs = [{"race": 9, "banker": {"name": "Turbo Power"},
             "savers": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}]
    out = apply_flagged_horses(legs, {9: ["Phutulicious"]})
    names = [s["name"] for s in out[0]["savers"]]
    assert "Phutulicious" in names
    assert len(names) == 3  # displaced, not added
    assert out[0].get("flagged_applied") is True


def test_flagged_already_covered_noop():
    legs = [{"race": 9, "banker": {"name": "Turbo Power"},
             "savers": [{"name": "Phutulicious"}]}]
    out = apply_flagged_horses(legs, {9: ["phutulicious"]})
    assert [s["name"] for s in out[0]["savers"]] == ["Phutulicious"]


@pytest.mark.parametrize("n,pools", [
    (1, []),
    (6, ["Exacta"]),
    (10, ["Exacta", "Trifecta"]),
    (14, ["Exacta", "Trifecta", "Quartet"]),
])
def test_suitability_gate(n, pools):
    race = {"runners": [{"name": f"H{i}", "prob": 0.4 if i == 0 else 0.05} for i in range(n)]}
    got = race_suitability(race)
    assert sorted(got.keys()) == sorted(pools)


def test_okf_textbook_entries_present():
    import re
    src = open("cloudflare_mcp_edge/src/generated/racing-knowledge.ts").read()
    for slug in ("exotics-pools", "exotics-construction", "exotics-case-friday-night"):
        assert slug in src, f"missing bundle entry: {slug}"
    # tracks index must not reference the closed Kimberley circuit
    tracks = open("cloudflare_mcp_edge/knowledge/racing/tracks/index.md").read()
    assert "lamingo" not in tracks
