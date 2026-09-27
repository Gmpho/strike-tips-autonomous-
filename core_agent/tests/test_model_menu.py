"""Telegram /model menu — live-verified models only, never retired IDs.

Sep-2026: the menu still advertised "Groq Llama 70B" long after Groq
retired the llama IDs (every call 404'd), and it lagged the HUD by a whole
model generation (Gemini 2.5 while the HUD ran 3.5/3.8). These tests pin the
menu to the shared live pool (agent/model_pool) and the alias → router-string
mapping.
"""

from core_agent.agent.model_menu import MENU_CHOICES, resolve_choice, render_menu
from core_agent.agent.model_pool import GEMINI_MODELS, GROQ_MODELS

_FLAGSHIP = GEMINI_MODELS[0]  # gemini-3.5-flash — the HUD default


def test_menu_lists_live_models_only():
    text = render_menu("auto")
    assert "GPT-OSS 120B" in text
    assert "GPT-OSS 20B" in text
    # HUD-parity generation: 3.5 flagship + 3.8 multimodal + Pro for maths.
    assert "Gemini 3.5 Flash" in text
    assert "Gemini 3.8 Flash" in text
    assert "Gemini Pro" in text
    # Retired IDs must never come back.
    assert "Llama" not in text
    assert "llama" not in text.lower()


def test_aliases_resolve_to_router_strings():
    assert resolve_choice("oss120") == GROQ_MODELS[0]
    assert resolve_choice("oss20") == GROQ_MODELS[1]
    assert resolve_choice("gemini") == _FLAGSHIP
    assert resolve_choice("auto") == "auto"
    # Legacy aliases resolve onto LIVE models, never back onto a dead ID.
    assert resolve_choice("groq") in GROQ_MODELS
    assert resolve_choice("OSS120") == GROQ_MODELS[0]  # case-insensitive
    assert resolve_choice("  oss20  ") == GROQ_MODELS[1]


def test_unknown_choice_returns_none():
    assert resolve_choice("llama-70b") is None
    assert resolve_choice("") is None
    assert resolve_choice("nonsense") is None


def test_menu_renders_current_selection():
    assert f"Current selection: *{_FLAGSHIP}*" in render_menu(_FLAGSHIP)


def test_menu_choices_have_unique_aliases():
    aliases = [alias for alias, _ in MENU_CHOICES]
    assert len(aliases) == len(set(aliases))
    assert aliases[0] == "auto"
