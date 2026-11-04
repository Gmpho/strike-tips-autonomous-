"""Prompt budget regression — locks in the Sep-2026 prompt diet.

Full asdict race cards with 12-field Betfair enrichment hit 9-14k tokens
per call against Groq's 8k TPM ceiling (413/429 + Gemini-fallback spend).
The slim projection must stay small no matter how much enrichment the
card carries. Token estimate: chars/4 (conservative for JSON).
"""

import json
from types import SimpleNamespace

import pytest

st = pytest.importorskip(
    "core_agent.core.strike_tips", reason="strike_tips unimportable"
)

GROQ_TPM_BUDGET = 6000  # tokens; headroom under the 8k ceiling per call


def _enriched_runner(i):
    return {
        "horse_name": f"Horse {i}",
        "odds_decimal": 5.0 + i,
        "form": "1-2-3",
        "jockey": "J Doe",
        "trainer": "T Smith",
        "barrier": (i % 14) + 1,
        "weight": 58.5,
        "gear": "Blinkers ON, Tongue Tie",
        "daysSinceRun": 21,
        "runner_comments": "Stayed on strongly over this trip last time, "
        "should appreciate the step up and the apprentice claim helps. " * 3,
        "official_rating": 95,
        "pedigree": "Some Sire x Some Dam (Some Damsire)",
        "owner": "Mr A Very Long Owner Name Syndicate (Nom: Someone)",
        "verdict": "Major player on form with solid claims throughout. " * 2,
    }


def _enriched_race(n_runners=16):
    return SimpleNamespace(
        track="vaal",
        race_number=5,
        distance=1600,
        track_condition="Good",
        runners=[_enriched_runner(i) for i in range(n_runners)],
    )


def _est_tokens(obj):
    return len(json.dumps(obj)) / 4


def test_slim_shape_contract():
    slim = st._slim_race_for_prompt(_enriched_race(), "vaal")
    assert set(slim.keys()) == {"track", "race_number", "distance",
                                "condition", "runners"}
    assert len(slim["runners"]) <= 14  # capped even for oversize fields
    for r in slim["runners"]:
        assert set(r.keys()) == {"horse", "odds", "form", "jockey", "trainer"}


def test_slim_stays_in_budget():
    slim = st._slim_race_for_prompt(_enriched_race(), "vaal")
    assert _est_tokens(slim) < 1500, f"slim race too big: {_est_tokens(slim):.0f}"


def test_diet_is_effective():
    """The full card must be materially bigger — else the diet is a no-op."""
    from dataclasses import asdict  # noqa (documents the old call shape)

    race = _enriched_race()
    full = {"track": race.track, "race_number": race.race_number,
            "distance": race.distance, "condition": race.track_condition,
            "runners": race.runners}
    slim = st._slim_race_for_prompt(race, "vaal")
    assert _est_tokens(full) > 2 * _est_tokens(slim)


def test_exotic_call_uses_live_model():
    src = open(st.__file__).read()
    assert '"model": "openai/gpt-oss-120b"' in src
