"""Telegram ``/model`` menu — single source of truth for chat model choices.

The pool mirrors the live-verified models (see ``ModelConfig``: the old
llama/deepseek Groq IDs are retired and 404, so they must never be offered
again) plus the Gemini fallback chain. ``resolve_choice`` maps user aliases
to the exact strings ``TaskRouter`` understands; the router hands explicit
Groq choices down to ``GroqProvider`` which honours them over its
tool-based heuristic.
"""

from typing import Dict, List, Optional, Tuple

# (alias, label) — rendered by /model with no arguments
MENU_CHOICES: List[Tuple[str, str]] = [
    ("auto", "⚡ Auto Router (optimal)"),
    ("oss120", "☁️ GPT-OSS 120B (tools + deep reasoning)"),
    ("oss20", "☁️ GPT-OSS 20B (fast reads)"),
    ("gemini", "☁️ Gemini 2.5 Flash"),
]

# alias → router model string
ALIASES: Dict[str, str] = {
    "auto": "auto",
    "oss120": "openai/gpt-oss-120b",
    "120b": "openai/gpt-oss-120b",
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
    "oss20": "openai/gpt-oss-20b",
    "20b": "openai/gpt-oss-20b",
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "openai/gpt-oss-20b": "openai/gpt-oss-20b",
    "gemini": "gemini",
    "gemini-2.5-flash": "gemini",
    "gemini-flash": "gemini",
    # Legacy alias — keeps old chats working; router auto-picks the
    # gpt-oss pair (20b for reads, 120b when tools are needed).
    "groq": "groq",
}


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
