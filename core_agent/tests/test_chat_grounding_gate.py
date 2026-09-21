"""Chat grounding gate + identity sanitization (Sep-2026).

Pins the fixes for two Telegram complaints:
  1. every reply carried the live race card even mid-conversation
     ("You good" → "36 races across 7 tracks"), and
  2. the agent described itself as a retired model ("I am powered by Groq's
     llama-3.3-70b-versatile") because old ChromaDB insights leaked through.
"""

import pytest

from core_agent.agent.context import wants_live_card, _TRIVIAL_PATTERNS
from core_agent.agent.prompts import sanitize_model_text, _identity_block


# ── Card-intent gate ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Hey", "You good", "What model are you", "What can you do",
    "thanks", "who are you", "How are you?", "nice",
])
def test_casual_turns_skip_card(text):
    assert wants_live_card(text) is False, f"casual turn gated wrongly: {text!r}"


@pytest.mark.parametrize("text", [
    "races at turffontein",
    "show me today's card",
    "Analyse this race for value betting opportunities:\n\nCourse: Greyville | Race 8 | Off Time: 15:15",
    "1. Hurricane Flight — 7.50 — Form: 653741-",
    "odds for kempton",
    "any value picks today?",
    "bipot legs for greyville",
])
def test_racing_turns_keep_card(text):
    assert wants_live_card(text) is True, f"racing turn lost card: {text!r}"


def test_trivial_patterns_cover_conversational_turns():
    for text in ["You good", "What model are you", "What can you do", "How are you"]:
        assert _TRIVIAL_PATTERNS.match(text), f"not trivial: {text!r}"


# ── Identity / stale-model sanitization ─────────────────────────────────────

def test_retired_models_rewritten():
    stale = ("Primary: Groq llama-3.3-70b-versatile for race analysis. "
             "Fallback: Gemini 2.5 flash. No deepseek or kimi providers.")
    out = sanitize_model_text(stale)
    assert "llama-3.3" not in out
    assert "deepseek" not in out.lower()
    assert "kimi" not in out.lower()
    assert "openai/gpt-oss-120b" in out
    assert "gemini" in out.lower()  # live fallback untouched


def test_identity_block_names_live_pool():
    from core_agent.config.model_config import ModelConfig

    block = _identity_block()
    assert ModelConfig.ORCHESTRATOR in block
    assert "retired" in block.lower()
    for dead in ("llama-3.3", "llama-3.1", "deepseek", "kimi"):
        assert dead not in block.split("overrides")[0]  # not claimed as current


def test_system_prompt_gates_race_card():
    from core_agent.agent.prompts import build_system_prompt

    casual = build_system_prompt(for_cloud=True, user_message="You good")
    assert "Live race card withheld" in casual

    racing = build_system_prompt(for_cloud=True, user_message="races at greyville")
    assert "withheld" not in racing
