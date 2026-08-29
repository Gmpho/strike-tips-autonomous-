"""Tests for swarm_researcher form-backfill (Tasks 2.1, 2.2, 2.6, 5.1, 5.2).

News linking is covered separately in test_news_linking.py. These tests are
fully hermetic — network (web search / Groq / Chroma) and disk writes are mocked.
"""

from datetime import datetime

from core_agent.skills import swarm_researcher as sr
from core_agent.skills.swarm_researcher import (
    MAX_GROQ_PER_CYCLE,
    WEB_GROUND_ODDS_CAP,
    _detect_region,
    backfill_form_insights,
    build_field_insight,
    enrich_snapshot_with_insights,
)


def _patch_backfill(monkeypatch, swarm_seed=None):
    """Mock all network/IO touched by backfill_form_insights."""
    monkeypatch.setattr(sr, "load_swarm_insights", lambda: dict(swarm_seed or {}))
    monkeypatch.setattr(sr, "save_swarm_insights", lambda data: None)
    monkeypatch.setattr(sr, "_fresh_insight_exists", lambda *a, **k: False)
    monkeypatch.setattr(sr, "_web_ground", lambda *a, **k: _await("web fact snippet"))
    monkeypatch.setattr(sr, "_groq_call", lambda *a, **k: _await("grounded summary"))
    monkeypatch.setattr(sr, "save_racing_insight", lambda *a, **k: True)


import asyncio


async def _await(value):
    return value


def _run(coro):
    return asyncio.run(coro)


# ── Task 2.1 — region detection ───────────────────────────────────────────────

def test_region_from_en_prefix():
    assert _detect_region({"en": "USA: Saratoga"}) == "USA"


def test_region_fallback_course_keyword():
    assert _detect_region({"course": "Turffontein"}) == "South Africa"


def test_region_unknown_default():
    assert _detect_region({"en": "Nowhere", "course": "Narnia"}) == "Unknown"


# ── Task 2.2 — deterministic field blurb ──────────────────────────────────────

def test_field_insight_contains_live_fields():
    runner = {"name": "Test Horse", "form": "123", "draw": 5, "age": "3yo", "weight": "9st 7lbs"}
    blurb = build_field_insight(runner)
    assert "form 123" in blurb
    assert "draw 5" in blurb
    assert "3yo" in blurb
    assert "9st 7lbs" in blurb


def test_field_insight_never_fabricates():
    runner = {"name": "Bare Runner"}
    blurb = build_field_insight(runner)
    assert blurb  # non-empty
    assert "no additional live data" in blurb


# ── Task 2.6 — swarm_insights cache round-trip (atomic write) ─────────────────

def test_swarm_insights_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "SWARM_INSIGHTS_PATH", str(tmp_path / "swarm_insights.json"))
    data = {"oid1": {"source": "field_only", "insight": "x", "ts": "2026-01-01T00:00:00"}}
    sr.save_swarm_insights(data)
    assert sr.load_swarm_insights() == data


# ── Task 5.1 — inline snapshot enrichment always runs ─────────────────────────

def test_enrich_stamps_missing_timeform_runners():
    state = {"events": {"e1": {
        "en": "USA: Saratoga", "course": "Saratoga",
        "runners": [{"name": "R1", "outcomeId": "o1"}, {"name": "R2", "timeForm": "stars"}],
    }}}
    enrich_snapshot_with_insights(state)
    r1 = state["events"]["e1"]["runners"][0]
    assert r1["region"] == "USA"
    assert r1["insightSource"] == "field_only"
    assert r1["swarmInsight"]  # non-empty deterministic blurb
    # Runner that already has timeForm is left untouched
    assert "swarmInsight" not in state["events"]["e1"]["runners"][1]


# ── Task 5.2 — gated upgrade budget cap + per-day cache ───────────────────────

def _gated_state(n, odds=2.0):
    runners = [
        {"name": f"H{i}", "outcomeId": f"o{i}", "odds": odds, "timeForm": ""}
        for i in range(n)
    ]
    return {"events": {"e1": {"en": "USA: Test", "course": "Test", "runners": runners}}}


def test_backfill_respects_groq_cap(monkeypatch):
    _patch_backfill(monkeypatch)
    calls = _run(backfill_form_insights(_gated_state(8)))
    assert calls == MAX_GROQ_PER_CYCLE  # capped at 6 even with 8 eligible runners


def test_backfill_per_day_cache_skips_today(monkeypatch):
    today = datetime.now().strftime("%Y-%m-%d")
    seed = {f"o{i}": {"ts": today} for i in range(4)}  # 4 of 8 already cached today
    _patch_backfill(monkeypatch, swarm_seed=seed)
    # Only the 4 uncached runners are gated → at most 4 Groq calls
    calls = _run(backfill_form_insights(_gated_state(8)))
    assert calls == 4


def test_backfill_ignores_high_odds_runners(monkeypatch):
    _patch_backfill(monkeypatch)
    # 6 runners all priced 10.0 (over WEB_GROUND_ODDS_CAP) → no web grounding
    calls = _run(backfill_form_insights(_gated_state(6, odds=10.0)))
    assert calls == 0
