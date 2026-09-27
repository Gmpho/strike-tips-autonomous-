"""Chat grounding — Sep-2026 hallucinations (Rand Stadium, Ohlange, wrong
dates, fantasy cards).

Re-baselined (Sep-2026 agent refactor moved the implementation): the card
intent gate now lives in ``core_agent.agent.context.wants_live_card`` and the
grounding in ``core_agent.agent.prompts.build_system_prompt`` /
``_build_race_context``. The SPEC (openspec/specs/chat-grounding) is
unchanged and still enforced here:

  * existence gate      — never ground a meeting we have no live card for
  * pasted-card passthrough — a user-supplied card is never gated
  * grounding prefix    — real date + real meetings on model-bound turns
  * card-intent gate    — casual turns must not carry the meeting list
"""

import pytest

ctx = pytest.importorskip("core_agent.agent.context", reason="context unimportable")
prompts = pytest.importorskip("core_agent.agent.prompts", reason="prompts unimportable")

wants_live_card = ctx.wants_live_card


def _race(course: str, race_no: int = 1, runners=()) -> dict:
    return {
        "course": course,
        "name": f"{course} R{race_no}",
        "en": f"{course} R{race_no}",
        "raceNumber": race_no,
        "runners": list(runners),
    }


def _patch_snapshot(monkeypatch, events: dict) -> None:
    import core_agent.core.snapshot_cache as sc

    monkeypatch.setattr(sc, "get_snapshot", lambda: {"events": events, "count": len(events)})


def test_pasted_card_is_never_gated():
    """Spec: pasted-card passthrough — a user-supplied card is analysed.

    The gate answers "does this turn need racing context?", NOT the old
    "should we fetch the live card?" (that helper is gone), so a pasted card
    is a TRUE — it is an analysis request and must never be refused.
    """
    pasted = ("Analyse this race for value: Dundalk R7. Runners: "
              "1. Coolnagrattan — 23.00 — Form: 308 — Reese Holohan")
    assert wants_live_card(pasted.lower()) is True


def test_asks_for_card_catches_transcripts():
    for q in ["uhmm what races we have today",
              "how many live races we have",
              "search latest races",
              "cool search latest races",
              "what races at rand stadium today",
              "show me today's card"]:
        assert wants_live_card(q) is True, q


def test_casual_turns_never_carry_the_card():
    """Greetings/filler must not pull racing context (Sep-2026 regression).

    Two layers: the card-intent gate (wants_live_card) and the
    ContextBuilder fast path (_TRIVIAL_PATTERNS) that skips heavy
    assembly for greetings entirely.
    """
    for q in ["hello", "hey", "hey, you good?", "you good",
              "how you doing today", "how are you doing",
              "how's it going today", "what's up", "whats up man",
              "cool", "cool thanks", "sweet thanks man", "good morning",
              "ok", "bye", "tell me a joke"]:
        assert wants_live_card(q) is False, q
    for q in ["hello", "hey, you good?", "how you doing today",
              "how's it going today", "whats up man", "cool thanks",
              "sweet thanks man", "good morning"]:
        assert ctx._TRIVIAL_PATTERNS.match(q), q


def test_fantasy_track_not_grounded(monkeypatch):
    """No live meeting named Rand Stadium -> the prompt must not invent one."""
    _patch_snapshot(monkeypatch, {})
    out = prompts.build_system_prompt(user_message="what races at rand stadium today")
    assert "rand stadium" not in out.lower()
    assert "0 total" in out  # the real (empty) card, not a fantasy one


def test_real_meetings_listed_not_invented(monkeypatch):
    _patch_snapshot(monkeypatch, {"a": _race("vaal"), "b": _race("turffontein", 2)})
    out = prompts.build_system_prompt(user_message="what races at ohlange today")
    assert "ohlange" not in out.lower()
    assert "vaal" in out.lower() and "turffontein" in out.lower()


def test_grounding_prefix_stamped(monkeypatch):
    """Model-bound turns carry the real date + real meetings."""
    from datetime import datetime

    _patch_snapshot(monkeypatch, {"a": _race("vaal")})
    out = prompts.build_system_prompt(user_message="what races at vaal today")
    assert "vaal" in out.lower()
    assert str(datetime.now().year) in out  # real date, not a guess


def test_casual_turn_omits_race_card(monkeypatch):
    """The card-intent gate: 'hey' must not ship the meeting list."""
    _patch_snapshot(monkeypatch, {"a": _race("vaal")})
    out = prompts.build_system_prompt(user_message="hey, you good?")
    assert "Live races today" not in out
    # ...while a genuine card ask still gets it.
    assert "Live races today" in prompts.build_system_prompt(
        user_message="what races are on today"
    )
