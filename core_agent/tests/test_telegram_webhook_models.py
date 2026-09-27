"""Telegram webhook /model parity with the AgentLoop menu (Sep-2026).

The deployed webhook (``modal_app.telegram_webhook``) answers auth/status/
help/chart/scan inline and forwards EVERY other message — including
``/model`` — onto the bus, where ``AgentLoop._handle_command`` renders the
shared ``model_menu``. There is deliberately no second menu: this file
guards that invariant so the "selection silently falls to Ollama" drift
bug cannot come back.
"""

from core_agent.config.model_config import ModelConfig


def _webhook_src() -> str:
    with open("core_agent/core/modal_app.py") as f:
        return f.read()


def _loop_src() -> str:
    with open("core_agent/agent/loop.py") as f:
        return f.read()


def _menu_src() -> str:
    with open("core_agent/agent/model_menu.py") as f:
        return f.read()


def test_webhook_menu_lists_live_models():
    src = _menu_src()
    assert "GPT-OSS 120B" in src
    assert "Llama 70B" not in src  # stale label gone


def test_webhook_has_no_inline_model_menu():
    """A second inline menu inside modal_app is exactly how drift starts."""
    src = _webhook_src()
    assert "gemini-turbo" not in src
    assert "gemini-lite" not in src
    assert 'cmd == "/model"' not in src  # /model falls through to the bus
    assert "bus.publish(inbound)" in src
    assert "model_menu" not in src  # webhook never renders its own menu


def test_webhook_menu_matches_loop_menu():
    """Same offered keys everywhere — the loop renders model_menu directly."""
    src = _loop_src()
    assert (
        "from core_agent.agent.model_menu import render_menu, resolve_choice"
        in src
    )
    from core_agent.agent.model_menu import ALIASES, MENU_CHOICES

    aliases = {alias for alias, _ in MENU_CHOICES}
    assert {"auto", "gemini"} <= aliases
    assert "groq" in ALIASES  # legacy alias kept alive too


def test_webhook_menu_uses_modelconfig():
    """/model pool must match the live ModelConfig, not stale literals."""
    assert ModelConfig.ORCHESTRATOR.startswith("openai/gpt-oss")
    assert ModelConfig.GROQ_FAST.startswith("openai/gpt-oss")
    menu_src = _menu_src()
    assert ModelConfig.ORCHESTRATOR in menu_src  # menu offers the live orchestrator
    assert ModelConfig.GROQ_FAST in menu_src
