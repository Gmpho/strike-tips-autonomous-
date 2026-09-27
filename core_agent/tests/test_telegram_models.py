"""Telegram /model menu mirrors the live cloud pool (Sep-2026).

Single source of truth: ``core_agent/agent/model_menu.py``. Every alias the
menu offers must resolve to a string ``TaskRouter`` understands — otherwise
the selection silently falls through to Ollama (the retired-IDs bug).
"""

import pytest

loop_mod = pytest.importorskip(
    "core_agent.agent.loop", reason="agent loop unimportable"
)
menu_mod = pytest.importorskip(
    "core_agent.agent.model_menu", reason="model menu unimportable"
)
tr = pytest.importorskip(
    "core_agent.agent.providers.task_router", reason="router unimportable"
)


def test_menu_lists_live_models():
    menu_src = open(menu_mod.__file__).read()
    assert "GPT-OSS 120B" in menu_src
    assert "Llama 70B" not in menu_src  # stale label gone

    loop_src = open(loop_mod.__file__).read()
    # The loop renders the SHARED menu — no second inline menu anywhere.
    assert "render_menu" in loop_src
    assert "resolve_choice" in loop_src


def test_every_menu_key_routes():
    """Each advertised alias must hit a provider branch, not the Ollama fallthrough."""
    router_src = open(tr.__file__).read()
    resolved = set()
    for alias, _label in menu_mod.MENU_CHOICES:
        mapped = menu_mod.resolve_choice(alias)
        assert mapped, f"menu alias does not resolve: {alias}"
        resolved.add(mapped)
    for mapped in resolved:
        if mapped == "auto":
            continue  # auto = no override; the router heuristic decides
        assert f'"{mapped}"' in router_src, f"router cannot resolve: {mapped}"
    # Legacy alias must keep old chats working.
    assert menu_mod.resolve_choice("groq") == "groq"


@pytest.mark.asyncio
async def test_model_command_roundtrip():
    from core_agent.agent.loop import AgentLoop
    from core_agent.agent.session import SessionManager
    from core_agent.bus.events import InboundMessage

    sent = []

    class FakeBus:
        async def publish_outbound(self, msg):
            sent.append(msg)

    loop = AgentLoop.__new__(AgentLoop)
    loop.bus = FakeBus()
    loop.session_mgr = SessionManager()
    mgr_session = loop.session_mgr.get("test-model")

    async def run(cmd):
        sent.clear()
        await loop._handle_command(
            InboundMessage(
                session_key="test-model",
                channel="t",
                chat_id="1",
                content=cmd,
            ),
            mgr_session,
        )
        return sent[-1].content if sent else ""

    out = await run("/model oss20")
    assert "openai/gpt-oss-20b" in out

    out = await run("/model groq")  # legacy alias still accepted
    assert "switched" in out.lower()
    assert "groq" in out

    out = await run("/model gemini-turbo")  # retired alias — must refuse
    assert "Unknown model" in out

    out = await run("/model")  # menu renders with the live pool
    assert "GPT-OSS 120B" in out
    assert "Current selection" in out
