"""Telegram ``/model`` menu — single source of truth for chat model choices.

Every entry resolves through :mod:`core_agent.agent.model_pool`, the pool the
HUD chat function shares, so ``/model gemini-3.5-flash`` on Telegram lands on
exactly the model the HUD would use. Retired IDs (the old llama/deepseek Groq
entries, gemini-1.5/2.0) are not offered and are not resolvable.
"""

from typing import Dict, List, Optional, Tuple

from core_agent.agent.model_pool import (
    GEMINI_MODELS,
    GROQ_MODELS,
    LEGACY_GEMINI_ALIASES,
    LEGACY_GROQ_ALIASES,
)

_FLAGSHIP = GEMINI_MODELS[0]          # gemini-3.5-flash (grounded, HUD default)
_MULTIMODAL = "gemini-3.8-flash"     # HUD's document master
_PRO = "gemini-3.1-pro-preview"       # deep maths / exotic combinatorics
_OSS120, _OSS20 = GROQ_MODELS

# (alias, label) — rendered by /model with no arguments
MENU_CHOICES: List[Tuple[str, str]] = [
    ("auto", "⚡ Auto Router (same picks as the HUD)"),
    ("oss120", "☁️ GPT-OSS 120B (tools + deep reasoning)"),
    ("oss20", "☁️ GPT-OSS 20B (fast reads)"),
    ("gemini", f"☁️ Gemini 3.5 Flash (grounded — {_FLAGSHIP})"),
    ("gemini38", f"☁️ Gemini 3.8 Flash (multimodal documents)"),
    ("deep", "🧮 Gemini Pro (pick 6 / jackpot / edge maths)"),
]

# alias → router model string
ALIASES: Dict[str, str] = {
    "auto": "auto",
    # Groq — full IDs plus the short forms people type.
    _OSS120: _OSS120,
    "oss120": _OSS120,
    "120b": _OSS120,
    "gpt-oss-120b": _OSS120,
    "openai/gpt-oss-120b": _OSS120,
    _OSS20: _OSS20,
    "oss20": _OSS20,
    "20b": _OSS20,
    "gpt-oss-20b": _OSS20,
    "openai/gpt-oss-20b": _OSS20,
    # Gemini — the flagship first, then the rest of the pool.
    "gemini": _FLAGSHIP,
    "gemini35": _FLAGSHIP,
    "3.5": _FLAGSHIP,
    "gemini-3.5-flash": _FLAGSHIP,
    "gemini38": _MULTIMODAL,
    "3.8": _MULTIMODAL,
    "gemini-3.8-flash": _MULTIMODAL,
    "deep": _PRO,
    "pro": _PRO,
    "gemini-pro": _PRO,
    _PRO: _PRO,
    "gemini-lite": "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",
    "gemini-2.5-flash": "gemini-2.5-flash",
}

# Old chat selections still resolve — onto the live pool, never a dead ID.
ALIASES.update(LEGACY_GEMINI_ALIASES)
ALIASES.update({k: v for k, v in LEGACY_GROQ_ALIASES.items()})


def resolve_choice(choice: str) -> Optional[str]:
    """Map a ``/model`` argument to a router model string, or None if unknown."""
    return ALIASES.get((choice or "").strip().lower())


def render_menu(current: str) -> str:
    """Format the ``/model`` help text with the current selection."""
    lines = [
        "🧠 *Select active model*",
        "To switch model, reply with `/model <name>`:",
        "",
    ]
    lines += [f"• `/model {alias}` — {label}" for alias, label in MENU_CHOICES]
    lines += ["", f"Current selection: *{current}*"]
    return "\n".join(lines)
