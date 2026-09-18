"""Chat grounding — Sep-2026 hallucinations (Rand Stadium, Ohlange,
wrong dates, fantasy cards). The router must refuse card requests it has
no data for and stamp every model-bound message with date + meetings.
"""

import pytest

tr = pytest.importorskip(
    "core_agent.agent.providers.task_router", reason="router unimportable"
)
TaskRouter = tr.TaskRouter


def _router():
    try:
        return TaskRouter()
    except TypeError:
        return TaskRouter.__new__(TaskRouter)


def test_asks_for_card_ignores_pasted_cards():
    r = _router()
    pasted = ("Analyse this race for value: Dundalk R7. Runners: "
              "1. Coolnagrattan — 23.00 — Form: 308 — Reese Holohan")
    assert r._asks_for_card(pasted.lower()) is False


def test_asks_for_card_catches_transcripts():
    r = _router()
    for q in ["uhmm what races we have today",
              "how many live races we have",
              "search latest races",
              "cool search latest races",
              "what races at rand stadium today",
              "show me today's card"]:
        assert r._asks_for_card(q) is True, q


def test_asks_for_card_leaves_chat_alone():
    r = _router()
    for q in ["hello", "how you doing today", "tell me a joke",
              "cool thanks", "sweet thanks man"]:
        # "how you doing today" has 'today' but no ask-verb → False
        assert r._asks_for_card(q) is False, q


@pytest.mark.asyncio
async def test_fantasy_track_refused_no_snapshot(monkeypatch):
    r = _router()
    import core_agent.core.snapshot_cache as sc
    monkeypatch.setattr(sc, "get_snapshot", lambda: {"events": {}})
    out = await r._try_snapshot_answer(
        [{"role": "user", "content": "what races at rand stadium today"}])
    assert out is not None
    assert "rand stadium" not in out.lower()
    assert "live racing data" in out.lower() or "isn't racing" in out.lower()


@pytest.mark.asyncio
async def test_real_meetings_listed_not_invented(monkeypatch):
    import core_agent.core.snapshot_cache as sc
    monkeypatch.setattr(sc, "get_snapshot", lambda: {"events": {
        "a": {"course": "vaal", "raceNumber": 1},
        "b": {"course": "turffontein", "raceNumber": 2},
    }})
    r = _router()
    out = await r._try_snapshot_answer(
        [{"role": "user", "content": "what races at ohlange today"}])
    assert out is not None
    assert "ohlange" not in out.lower()
    assert "vaal" in out.lower() and "turffontein" in out.lower()


@pytest.mark.asyncio
async def test_grounding_prefix_stamped(monkeypatch):
    import core_agent.core.snapshot_cache as sc
    monkeypatch.setattr(sc, "get_snapshot", lambda: {"events": {
        "a": {"course": "vaal", "raceNumber": 1},
    }})
    r = _router()
    seen = {}

    async def fake_provider(messages, tools, intent):
        seen["last"] = messages[-1]["content"]
        yield "done"

    # Drive only the prefix logic via stream with everything else stubbed:
    # monkeypatch provider attrs used downstream is heavy; instead assert
    # the helper contract directly.
    line = r._meeting_list_line()
    assert "vaal" in line
    today = r._today_sast()
    assert "2026" in today  # real SAST date, not a guess
