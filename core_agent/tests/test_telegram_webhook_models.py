"""Telegram webhook /model parity with the AgentLoop menu (Sep-2026).

The deployed Telegram path (modal_app telegram_webhook) answers inline and
does NOT run AgentLoop._handle_command — so every /model key offered HERE
must also resolve in TaskRouter's explicit override tuples. Drift between
the two menus revives the "selection silently falls to Ollama" bug.
"""

import ast

from core_agent.config.model_config import ModelConfig


def _menu_src() -> str:
    with open("core_agent/core/modal_app.py") as f:
        return f.read()


def _loop_src() -> str:
    with open("core_agent/agent/loop.py") as f:
        return f.read()


def test_webhook_menu_lists_live_models():
    src = _menu_src()
    assert "GPT-OSS 120B" in src
    assert "Llama 70B" not in src  # stale label gone


def test_webhook_mapping_resolves_in_router():
    """Each webhook mapping value must hit a TaskRouter provider branch."""
    tree = ast.parse(_menu_src())
    mapping = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [
                k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
            if {"auto", "groq", "gemini", "gemini-lite", "gemini-turbo"} <= set(keys):
                for k, v in zip(node.keys, node.values):
                    if isinstance(v, ast.Constant):
                        mapping[k.value] = v.value
    assert mapping, "webhook /model mapping not found"
    router_src = open("core_agent/agent/providers/task_router.py").read()
    for key, val in mapping.items():
        assert f'"{val}"' in router_src, (
            f"/model {key} -> {val!r} has no TaskRouter branch"
        )


def test_webhook_menu_matches_loop_menu():
    """Same offered keys in both menus — no orphan selections either way."""
    for choice in ["auto", "groq", "gemini", "gemini-lite", "gemini-turbo"]:
        assert f'"{choice}"' in _menu_src(), f"webhook missing /model {choice}"
        assert f'"{choice}"' in _loop_src(), f"loop missing /model {choice}"


def test_webhook_menu_uses_modelconfig():
    """/model menu pricing labels derive from ModelConfig, not literals."""
    src = _menu_src()
    assert "ModelConfig" in src
    assert ModelConfig.ORCHESTRATOR.startswith("openai/gpt-oss")