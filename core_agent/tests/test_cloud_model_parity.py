"""Telegram <-> HUD cloud-model parity + typing-indicator coverage (Sep-2026).

Two guarantees:

1. PARITY — Telegram must be able to select and auto-route to exactly the
   models the HUD chat function uses. ``model_pool`` is the single source of
   truth; the HUD twin (``resolveAutoModel`` in functions/api/chat.ts) is
   asserted to stay inside the same pool so the two can't drift again.
2. TYPING — both transports must re-arm the typing indicator for the whole
   model call (telegram-hud-ux spec: ~4s loop in webhook AND polling).
"""

import asyncio
import re

import pytest

pool = pytest.importorskip("core_agent.agent.model_pool", reason="model pool unimportable")
menu = pytest.importorskip("core_agent.agent.model_menu", reason="model menu unimportable")
groq = pytest.importorskip("core_agent.agent.providers.groq", reason="groq unimportable")
gemini = pytest.importorskip("core_agent.agent.providers.gemini", reason="gemini unimportable")
tg = pytest.importorskip("core_agent.channels.telegram", reason="telegram channel unimportable")
router = pytest.importorskip(
    "core_agent.agent.providers.task_router", reason="router unimportable"
)

HUD_CHAT_FN = "strike-tips-hud/functions/api/chat.ts"


def _hud_src() -> str:
    with open(HUD_CHAT_FN) as f:
        return f.read()


# ── 1. parity ──────────────────────────────────────────────────────────────

def test_providers_use_the_shared_pool():
    """No provider may keep its own model list (that is how they drifted)."""
    assert groq.GroqProvider.MODELS == list(pool.GROQ_MODELS)
    assert gemini.GeminiProvider.MODELS == list(pool.GEMINI_MODELS)


def test_gemini_flagship_is_the_hud_default():
    """gemini-3.5-flash is the HUD's default target and must be MODELS[0]."""
    assert gemini.GeminiProvider.MODELS[0] == "gemini-3.5-flash"
    assert "let targetModel = 'gemini-3.5-flash'" in _hud_src()


def test_every_hud_model_is_in_the_pool():
    """Any Gemini/Groq model the HUD can pick must exist in model_pool."""
    src = _hud_src()
    referenced = set(re.findall(r"gemini-[0-9][\w.-]*", src))
    referenced |= set(re.findall(r"openai/gpt-oss-[\w-]+", src))
    known = set(pool.GEMINI_MODELS) | set(pool.GROQ_MODELS)
    unknown = {m for m in referenced if m not in known}
    assert not unknown, f"HUD references models outside the shared pool: {sorted(unknown)}"


def test_menu_aliases_all_resolve_into_the_pool():
    for alias, _label in menu.MENU_CHOICES:
        target = menu.resolve_choice(alias)
        assert target, f"menu alias does not resolve: {alias}"
        if target == "auto":
            continue
        assert target in set(pool.GEMINI_MODELS) | set(pool.GROQ_MODELS), (
            f"/model {alias} -> {target!r} is not a live pool model"
        )


def test_legacy_gemini_alias_gets_the_flagship():
    """Old chats that picked 'gemini' must land on the HUD's flagship."""
    assert menu.resolve_choice("gemini") == "gemini-3.5-flash"


def test_retired_ids_are_not_offered():
    src = " ".join(label for _a, label in menu.MENU_CHOICES)
    for dead in ("Llama", "DeepSeek", "Mixtral", "Gemini 1.5", "Gemini 2.0"):
        assert dead not in src


@pytest.mark.parametrize(
    "question,expected",
    [
        ("build me a pick 6 bet with monte carlo", ("gemini-3.1-pro-preview", False)),
        # The HUD rule is the literal phrase "calculate edge" — a "the" in
        # between deliberately does NOT trip the deep-math branch.
        ("calculate edge for horse A at 6.0", ("gemini-3.1-pro-preview", False)),
        ("what is my balance", ("openai/gpt-oss-20b", True)),
        ("hello", ("openai/gpt-oss-20b", True)),
        ("give me a fast summary of the card", ("openai/gpt-oss-120b", True)),
        ("who wins the Woodbine feature race today?", ("gemini-3.5-flash", False)),
    ],
)
def test_auto_routing_matches_the_hud_rules(question, expected):
    assert pool.resolve_auto_model(question) == expected


def test_auto_routing_degrades_without_keys():
    assert pool.resolve_auto_model("build a jackpot system", has_gemini=False) == (
        "openai/gpt-oss-120b",
        True,
    )
    assert pool.resolve_auto_model("what is my balance", has_groq=False) == (
        "gemini-3.1-flash-lite",
        False,
    )


def test_router_honours_a_gemini_override():
    """The router must pass model_override through to the provider.

    It used to drop the argument, so `/model gemini-3.5-flash` silently
    answered with the provider default.
    """
    src = open(router.__file__).read()
    assert "model_override=gemini_target" in src
    # ...and the whitelist must be pool-driven, not a hardcoded tuple that
    # stops at 2.5 (the drift this test exists to prevent).
    assert "GEMINI_MODELS" in src
    assert '("gemini", "gemini-2.5-flash"' not in src


# ── 2. typing indicator ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_typing_loop_repeats_until_cancelled():
    """One send_chat_action is not enough — Telegram drops it after ~5s."""
    calls = []

    class FakeBot:
        async def send_chat_action(self, chat_id, action):
            calls.append((chat_id, action))

    task = asyncio.create_task(
        tg.telegram_typing_loop(FakeBot(), "42", interval_secs=0.01)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 2, f"typing must re-arm, got {len(calls)} call(s)"
    assert all(action == "typing" and chat == "42" for chat, action in calls)


@pytest.mark.asyncio
async def test_typing_loop_survives_a_bot_error():
    class BrokenBot:
        async def send_chat_action(self, chat_id, action):
            raise RuntimeError("network down")

    # Must return quietly (never raise) so the reply path is unaffected.
    await tg.telegram_typing_loop(BrokenBot(), "42", interval_secs=0.01)


def test_polling_path_wires_the_typing_lifecycle():
    """Regression guard: both transports arm and disarm the typing dot."""
    polling = open(tg.__file__).read()
    assert "self._start_typing(chat_id)" in polling
    assert "self._stop_typing(out.chat_id)" in polling

    webhook = open("core_agent/core/modal_app.py").read()
    assert 'send_chat_action(chat_id=c_id, action="typing")' in webhook
    assert "typing_task.cancel()" in webhook
    """Old chats that picked 'gemini' must land on the HUD's flagship."""
    assert menu.resolve_choice("gemini") == "gemini-3.5-flash"


def test_retired_ids_are_not_offered():
    src = " ".join(label for _a, label in menu.MENU_CHOICES)
    for dead in ("Llama", "DeepSeek", "Mixtral", "Gemini 1.5", "Gemini 2.0"):
        assert dead not in src
