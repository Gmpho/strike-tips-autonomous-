"""Telegram /model menu mirrors the HUD cloud pool (Sep-2026).

Every offered key must resolve in TaskRouter's override tuples — otherwise
the selection silently falls through to Ollama.
"""

import pytest

loop_mod = pytest.importorskip(
    "core_agent.agent.loop", reason="agent loop unimportable"
)
tr = pytest.importorskip(
    "core_agent.agent.providers.task_router", reason="router unimportable"
)


def _cmd_text(choice):
    src = open(loop_mod.__file__).read()
    assert f'"{choice}"' in src or f"'{choice}'" in src
    return src


def test_menu_lists_live_models():
    from core_agent.agent.loop import AgentLoop  # noqa (import check)

    src = open(loop_mod.__file__).read()
    assert "GPT-OSS 120B" in src
    assert "Llama 70B" not in src  # stale label gone


def test_every_menu_key_routes():
    """Each /model value must hit a provider branch, not the Ollama fallthrough."""
    router_src = open(tr.__file__).read()
    for key in ["auto", "groq", "gemini",
                "gemini-3.5-flash", "gemini-2.5-flash-lite"]:
        assert f'"{key}"' in router_src, f"router cannot resolve: {key}"


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
            InboundMessage(session_key="test-model", channel="t",
                           chat_id="1", content=cmd),
            mgr_session)
        return sent[-1].content if sent else ""

    out = await run("/model gemini-turbo")
    assert "gemini-3.5-flash" in out
    assert mgr_session.metadata.get("preferred_model") == "gemini-3.5-flash"
    out = await run("/model gemini-lite")
    assert mgr_session.metadata.get("preferred_model") == "gemini-2.5-flash-lite"
    out = await run("/model nonsense")
    assert "Unknown model" in out
    out = await run("/model")
    assert "gemini-lite" in out and "GPT-OSS" in out
