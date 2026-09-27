"""Telegram /model menu — live-verified models only, never retired IDs.

Sep-2026: the menu still advertised "Groq Llama 70B" long after Groq
retired the llama IDs (every call 404'd). These tests pin the menu to
the live pool and the alias → router-string mapping.
"""

from core_agent.agent.model_menu import MENU_CHOICES, resolve_choice, render_menu


def test_menu_lists_live_models_only():
    text = render_menu("auto")
    assert "GPT-OSS 120B" in text
    assert "GPT-OSS 20B" in text
    assert "Gemini 2.5 Flash" in text
    # Retired IDs must never come back.
    assert "Llama" not in text
    assert "llama" not in text.lower()


def test_aliases_resolve_to_router_strings():
    assert resolve_choice("oss120") == "openai/gpt-oss-120b"
    assert resolve_choice("oss20") == "openai/gpt-oss-20b"
    assert resolve_choice("gemini") == "gemini"
    assert resolve_choice("auto") == "auto"
    assert resolve_choice("groq") == "groq"  # legacy alias kept
    assert resolve_choice("OSS120") == "openai/gpt-oss-120b"  # case-insensitive
    assert resolve_choice("  oss20  ") == "openai/gpt-oss-20b"


def test_unknown_choice_returns_none():
    assert resolve_choice("llama-70b") is None
    assert resolve_choice("") is None
    assert resolve_choice("nonsense") is None


def test_menu_renders_current_selection():
    assert "Current selection: *gemini*" in render_menu("gemini")


def test_menu_choices_have_unique_aliases():
    aliases = [alias for alias, _ in MENU_CHOICES]
    assert len(aliases) == len(set(aliases))
    assert aliases[0] == "auto"
