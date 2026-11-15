"""Honcho id sanitisation.

Honcho rejects any peer/session id that does not match ``^[a-zA-Z0-9_-]+$``.
Because the Honcho layer is best-effort, that rejection was swallowed as a
single warning line, so deep memory silently never initialised for every
API-created user — their id is ``user_api:race_<n>_<ts>`` and the colon fails
the pattern. Nov-2026 production logged five of these per day.
"""

import re

import pytest

from core_agent.skills.memory.honcho_memory import (
    HonchoMemory,
    _PEER_ID_MAX,
    _honcho_id,
)

HONCHO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def test_api_style_id_is_sanitised():
    """The exact production offender: a colon between user_api and the race."""
    out = _honcho_id("user_api:race_17481932_1794688381153", prefix="user_")
    assert HONCHO_ID_PATTERN.match(out), out
    assert out.startswith("user_user_api_race_")
    assert "17481932" in out


def test_cosmetic_ids_are_left_alone():
    """Existing peers keep their history — only impossible ids get rewritten."""
    assert _honcho_id("anon_web", prefix="user_") == "user_anon_web"
    assert _honcho_id("123456789", prefix="user_") == "user_123456789"
    assert _honcho_id("race_1_2", prefix="user_") == "user_race_1_2"


def test_sanitising_is_idempotent():
    once = _honcho_id("a:b/c d")
    assert once == "a_b_c_d"
    assert _honcho_id(once) == once


def test_empty_and_none_fall_back_to_anon():
    assert _honcho_id("", prefix="user_") == "user_anon"
    assert _honcho_id(None, prefix="user_") == "user_anon"
    assert _honcho_id(":::", prefix="user_") == "user_anon"


def test_unicode_is_replaced_not_dropped():
    out = _honcho_id("kenilworth-café", prefix="user_")
    assert HONCHO_ID_PATTERN.match(out), out
    assert "kenilworth" in out


def test_long_ids_are_bounded_and_stay_distinct():
    """Truncation must not collapse two different users onto one peer."""
    head = "race_" + "9" * 120
    a = _honcho_id(head + "_alpha", prefix="user_")
    b = _honcho_id(head + "_beta", prefix="user_")
    assert len(a) <= _PEER_ID_MAX
    assert len(b) <= _PEER_ID_MAX
    assert a != b
    assert HONCHO_ID_PATTERN.match(a) and HONCHO_ID_PATTERN.match(b)


class _FakeClient:
    def __init__(self):
        self.peer_ids = []

    def peer(self, peer_id):
        self.peer_ids.append(peer_id)
        return object()

    def session(self, session_id):
        return object()


def _bare_memory(user_id: str) -> HonchoMemory:
    """Build HonchoMemory without touching the JSONL session directory."""
    mem = HonchoMemory.__new__(HonchoMemory)
    mem._user_id = user_id
    mem._honcho = None
    mem._user_peer = None
    mem._agent_peer = None
    return mem


def test_user_peer_uses_the_sanitised_id(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(
        "core_agent.skills.memory.honcho_memory._make_honcho_client",
        lambda: client,
    )
    mem = _bare_memory("user_api:race_17481932_1794688381153")

    assert mem._ensure_honcho() is True
    user_peer_id, agent_peer_id = client.peer_ids
    assert HONCHO_ID_PATTERN.match(user_peer_id), user_peer_id
    assert HONCHO_ID_PATTERN.match(agent_peer_id), agent_peer_id


def test_session_id_uses_the_sanitised_id(monkeypatch):
    monkeypatch.setattr(
        "core_agent.skills.memory.honcho_memory._make_honcho_client",
        lambda: _FakeClient(),
    )
    mem = _bare_memory("user_api:race_17481932_1794688381153")
    session_id = mem._honcho_session_id()
    assert ":" not in session_id
    assert " " not in session_id
    assert session_id.startswith("user_user_api_race_")
