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


# ── /model override threading (Sep-2026: providers dropped explicit ids) ──

def test_gemini_provider_honors_override():
    from core_agent.agent.providers.gemini import GeminiProvider
    import inspect

    sig = inspect.signature(GeminiProvider.stream)
    assert "model_override" in sig.parameters
    src = inspect.getsource(GeminiProvider.stream)
    # explicit id wins over the fallback chain head
    assert "model_override if model_override in self.MODELS" in src


def test_groq_provider_honors_override():
    from core_agent.agent.providers.groq import GroqProvider
    import inspect

    sig = inspect.signature(GroqProvider.stream)
    assert "model_override" in sig.parameters


@pytest.mark.asyncio
async def test_task_router_threads_override_to_gemini():
    """gemini-3.1-flash-lite selection must reach the provider call (not
    be dropped at the boundary — the /model confirmation lied before)."""
    from core_agent.agent.providers.gemini import GeminiProvider

    prov = GeminiProvider()
    prov.api_key = "test"

    # `model` is read from the enclosing scope at call time — patch the
    # module-level helper the provider uses to fetch its HTTP client, then
    # capture the URL the provider actually POSTs to (contains the model id).
    import core_agent.agent.providers.gemini as gmod
    captured = {}

    class FakeClient:
        async def post(self, url, json=None, **k):
            captured["url"] = url
            r = type("R", (), {})()
            r.status_code = 200
            r.raise_for_status = lambda: None
            r.json = lambda: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
            return r

    gmod.get_async_client = lambda timeout=None: FakeClient()

    msgs = [{"role": "user", "content": "You good"}]
    chunks = [c async for c in prov.stream(
        msgs, None, None, model_override="gemini-2.5-flash-lite")]
    assert chunks
    assert "gemini-2.5-flash-lite:generateContent" in captured["url"]


@pytest.mark.asyncio
async def test_snapshot_answer_does_not_serve_tomorrow_as_today():
    """'what races we have tomorrow' must not print today's card."""
    from core_agent.agent.providers.task_router import TaskRouter

    r = TaskRouter.__new__(TaskRouter)
    msgs = [{"role": "user", "content": "[QUERY]\ncool what races we have tomorrow"}]
    out = await r._try_snapshot_answer(msgs)
    if out:
        assert "Tomorrow" in out or "tomorrow" in out.lower()


@pytest.mark.asyncio
async def test_scan_request_not_answered_with_card():
    """'run a full daily scan across all 26 races' must not print the card."""
    from core_agent.agent.providers.task_router import TaskRouter

    r = TaskRouter.__new__(TaskRouter)
    r.ollama = None
    r.cloud_providers = []
    msgs = [{"role": "user", "content":
             "run a full daily scan across all 26 races at the listed tracks to identify value selections."}]
    out = await r._try_snapshot_answer(msgs)
    assert out is not None
    assert "Today's Racing" not in out
    assert "scan" in out.lower()
