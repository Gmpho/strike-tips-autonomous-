"""Dream scoring ledger, calibration, deterministic tier, prompt cache."""
import asyncio
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from core_agent.core import llm_cache
from core_agent.skills.dreamer import (
    _scenario_family,
    calculate_scenario_shift,
    calibrate_dreams,
)


def test_scenario_family():
    assert _scenario_family("What if the going changed to Heavy?") == "going"
    assert _scenario_family("Simulating a 20km/h headwind") == "wind"
    assert _scenario_family("What if the favourite was scratched?") == "scratch"
    assert _scenario_family("Calculating edge drift if market opens late") == "sentiment"
    assert _scenario_family("Analysing outsider value") == "sentiment"
    assert _scenario_family("") == "other"


def test_deterministic_shift_has_no_randomness():
    # Empty insight + deterministic Tier-1: always exactly 0.0.
    vals = {
        calculate_scenario_shift("Calculating edge drift late", {}, "", deterministic=True)
        for _ in range(20)
    }
    assert vals == {0.0}
    # Same call non-deterministic legacy path stays numeric (not asserted exact).
    v = calculate_scenario_shift("Calculating edge drift late", {}, "")
    assert isinstance(v, float)


def test_shift_reads_enriched_text():
    # Bare form string misses mud; enriched Betfair comment catches it.
    s = "What if the going changed to Heavy at Vaal?"
    assert calculate_scenario_shift(s, {"form": "5675-"}, "", deterministic=True) == -0.05
    assert calculate_scenario_shift(
        s, {"form": "5675-"}, "",
        extra_text="comment: stays on well in the mud", deterministic=True) == 0.08


def test_calibrate_scores_families(tmp_path):
    ledger = [
        {"dream_id": "a", "date": "2026-09-16", "track": "vaal", "race": "2",
         "family": "going", "fav": "Muddy Winner", "odds": 4.0,
         "implied": 0.25, "predicted": 0.33},
        {"dream_id": "b", "date": "2026-09-16", "track": "vaal", "race": "3",
         "family": "going", "fav": "Also Ran", "odds": 4.0,
         "implied": 0.25, "predicted": 0.9},
        {"dream_id": "c", "date": "2026-09-16", "track": "vaal", "race": "9",
         "family": "wind", "fav": "Ghost", "odds": 3.0,
         "implied": 0.33, "predicted": 0.4},
    ]
    winners = [
        {"date": "2026-09-16", "track": "vaal", "race": "2", "winner": "Muddy Winner"},
        {"date": "2026-09-16", "track": "vaal", "race": "3", "winner": "Someone Else"},
    ]
    (tmp_path / "dream_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in ledger))
    (tmp_path / "settled_winners.jsonl").write_text("\n".join(json.dumps(r) for r in winners))
    out = calibrate_dreams(str(tmp_path))
    # going: dream a brier (0.33-1)^2=0.4489 vs base (0.25-1)^2=0.5625;
    # dream b brier (0.9-0)^2=0.81 vs base (0.25-0)^2=0.0625
    assert out["going"]["n"] == 2
    assert out["going"]["skill"] == pytest.approx(
        ((0.5625 + 0.0625) - (0.4489 + 0.81)) / 2, abs=1e-3)
    # wind dream has no matching winner -> skipped entirely
    assert "wind" not in out
    assert (tmp_path / "dream_calibration.json").exists()


def test_llm_cache_roundtrip_and_scope(tmp_path):
    llm_cache.put(str(tmp_path), "m", "prompt-1", "resp-1")
    assert llm_cache.get(str(tmp_path), "m", "prompt-1") == "resp-1"
    assert llm_cache.get(str(tmp_path), "m", "prompt-2") is None
    assert llm_cache.get(str(tmp_path), "other-model", "prompt-1") is None
    # Yesterday's entries are invisible (midnight TTL).
    import datetime
    store = json.loads((tmp_path / "llm_cache.json").read_text())
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    for v in store.values():
        v["date"] = yesterday
    (tmp_path / "llm_cache.json").write_text(json.dumps(store))
    assert llm_cache.get(str(tmp_path), "m", "prompt-1") is None


def test_llm_cache_never_raises(tmp_path):
    assert llm_cache.get("/nonexistent-dir-xyz", "m", "p") is None
    llm_cache.put("/nonexistent-dir-xyz", "m", "p", "r")  # must not raise


def test_race_has_bets_gating():
    from core_agent.skills.dreamer import _race_has_bets
    import core_agent.skills.dreamer as _dm

    gov = MagicMock()
    b = MagicMock()
    b.status = "PENDING"
    b.track = "Vaal"
    b.race_number = 2
    gov.get_open_bets.return_value = [b]
    fake_brain = MagicMock()
    fake_brain.strike.bankroll = gov
    with patch.dict(sys.modules, {"core_agent.core.strike_brain": MagicMock(brain=fake_brain)}):
        # NOTE: dreamer does `from ... import brain`, binding name `brain`;
        # patch the already-imported reference instead.
        with patch.object(_dm, "brain", fake_brain, create=True):
            assert _race_has_bets("vaal", 2) is True
            assert _race_has_bets("vaal", 5) is False


def test_generate_dream_tier1_no_llm():
    from core_agent.skills.dreamer import DreamEngine
    import core_agent.skills.dreamer as _dm

    async def _no_llm(*a, **k):
        raise AssertionError("Groq must not be called in Tier-1")

    eng = DreamEngine()
    with patch.object(_dm, "_load_snapshot", return_value={
            "events": {"e1": {"course": "Vaal", "raceNumber": 2,
                              "runners": [{"name": "Test Horse", "odds": 4.0}]}}}):
        with patch.object(_dm, "_race_has_bets", return_value=False):
            with patch.object(_dm, "_groq_insight", new=_no_llm):
                with patch.object(_dm, "_enriched_race_text", return_value=""):
                    dream = asyncio.run(eng.generate_dream())
    assert "Tier-1" in dream.insight
    assert isinstance(dream.probability_shift, float)
