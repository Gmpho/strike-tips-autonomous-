"""Honcho ID sanitizer + Chroma transient retry (Sep-2026 log spam).

- Honcho rejects peer/session IDs outside ^[a-zA-Z0-9_-]+$; HUD session
  IDs look like 'api:session_17897...' (colon) and 422'd every peer init.
- Chroma Cloud throws transient SSL EOF / 408s; search must retry then
  fail soft, not error-spam the scan/chat path.
"""

import pytest

hm = pytest.importorskip(
    "core_agent.skills.memory.honcho_memory", reason="honcho_memory unimportable"
)


def test_safe_id_strips_colons():
    assert hm._safe_honcho_id("api:session_1789744383378") == "api-session_1789744383378"


def test_safe_id_keeps_valid():
    assert hm._safe_honcho_id("agent_strike") == "agent_strike"
    assert hm._safe_honcho_id("5398642046") == "5398642046"


def test_safe_id_fallbacks():
    assert hm._safe_honcho_id("") == "anon"
    assert hm._safe_honcho_id(":::") == "anon"
    assert hm._safe_honcho_id(None) == "anon"


def test_safe_id_matches_honcho_pattern():
    import re

    for raw in ["api:session_1", "user@x.com", "a b/c", "ok-1_2"]:
        assert re.match(r"^[a-zA-Z0-9_-]+$", hm._safe_honcho_id(raw)), raw


def test_session_id_sanitised():
    m = hm.HonchoMemory.__new__(hm.HonchoMemory)
    m._user_id = "api:session_1789744383378"
    sid = hm.HonchoMemory._honcho_session_id(m)
    import re

    assert ":" not in sid
    assert re.match(r"^[a-zA-Z0-9_-]+$", sid)


def test_chroma_search_retries_then_soft_fails(monkeypatch):
    cm = pytest.importorskip(
        "core_agent.skills.memory.chroma_memory", reason="chroma_memory unimportable"
    )
    mem = cm.RacingMemory.__new__(cm.RacingMemory)
    mem._is_ready = True
    calls = []

    class Flaky:
        def query(self, **kw):
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("SSL EOF")
            return {"documents": [["d"]], "metadatas": [[{}]], "distances": [[0.1]]}

    mem._form_collection = Flaky()
    monkeypatch.setattr("time.sleep", lambda s: None)
    out = cm.RacingMemory.search_form_insights(mem, "vaal")
    assert out == [{"content": "d", "metadata": {}, "distance": 0.1}]
    assert len(calls) == 3


def test_chroma_search_gives_up_quietly(monkeypatch, caplog):
    cm = pytest.importorskip(
        "core_agent.skills.memory.chroma_memory", reason="chroma_memory unimportable"
    )
    mem = cm.RacingMemory.__new__(cm.RacingMemory)
    mem._is_ready = True

    class Dead:
        def query(self, **kw):
            raise TimeoutError("408")

    mem._form_collection = Dead()
    monkeypatch.setattr("time.sleep", lambda s: None)
    with caplog.at_level("WARNING", logger="core_agent.skills.memory.chroma_memory"):
        assert cm.RacingMemory.search_form_insights(mem, "vaal") == []
    assert not [r for r in caplog.records if r.levelname == "ERROR"]
