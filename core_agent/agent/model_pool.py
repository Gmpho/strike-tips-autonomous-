"""Cloud model pool — the single source of truth for chat routing.

Telegram (TaskRouter) and the HUD (functions/api/chat.ts) MUST answer the
same question with the same model. ``resolve_auto_model`` below mirrors
``resolveAutoModel()`` in the HUD's chat function 1:1; the two are twins and
``tests/test_cloud_model_parity.py`` locks the mapping so they cannot drift.

Every ID here was verified live against the providers' model APIs on
2026-09-27. Retired IDs (llama-*, deepseek-*, mixtral, gemini-1.5/2.0) 404
and must never come back — the Telegram /model menu is built from this pool.
"""

from __future__ import annotations

# Groq production pool (tool calling + reasoning).
GROQ_MODELS: tuple[str, ...] = (
    "openai/gpt-oss-120b",  # tools / deep reasoning
    "openai/gpt-oss-20b",   # fast reads
)

# Gemini pool, flagship first — MODELS[0] is the default for every Gemini
# call and the first entry of the provider's fallback chain.
GEMINI_MODELS: tuple[str, ...] = (
    "gemini-3.5-flash",        # grounded flagship (HUD + Telegram default)
    "gemini-3.8-flash",        # multimodal document master
    "gemini-3.1-pro-preview",  # deep maths / exotic combinatorics
    "gemini-3.1-flash-lite",   # short factual answers
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)

# Legacy Telegram selections kept resolvable so old chats don't break. They
# map onto the live pool (never back onto a dead ID).
LEGACY_GROQ_ALIASES: dict[str, str] = {
    "groq": "openai/gpt-oss-120b",
    "groq-llama": "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "deepseek-r1-distill-llama-70b": "openai/gpt-oss-120b",
}

LEGACY_GEMINI_ALIASES: dict[str, str] = {
    "gemini": "gemini-3.5-flash",
    "gemini-2.0-flash": "gemini-2.5-flash",
    "gemini-1.5-flash": "gemini-2.5-flash",
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
}

# ── Auto routing (mirrors resolveAutoModel in functions/api/chat.ts) ─────────

# Deep maths / exotic combinatorics -> Gemini Pro, Groq 120B as backup.
_DEEP_MATH_TERMS = (
    "pick 6", "jackpot", "trifecta", "bipot", "kelly", "calculate edge",
    "mathematical", "monte carlo", "permutation", "compare runners",
    "system value", "combinations",
)

# Short factual chit-chat -> the cheap models.
_QUICK_TERMS = ("balance", "time", "hello", "rules", "what is", "help", "status", "ping")

_FAST_TERMS = ("fast", "quick summary")


def resolve_auto_model(
    text: str, has_gemini: bool = True, has_groq: bool = True
) -> tuple[str, bool]:
    """Pick the chat model for a turn. Returns ``(model_id, is_groq)``.

    Kept byte-compatible in behaviour with the HUD's ``resolveAutoModel``:
    Telegram and the HUD must land on the same model for the same question.
    """
    q = (text or "").lower()
    if any(t in q for t in _DEEP_MATH_TERMS):
        if has_gemini:
            return "gemini-3.1-pro-preview", False
        if has_groq:
            return "openai/gpt-oss-120b", True
    if len(q) < 50 and any(t in q for t in _QUICK_TERMS):
        if has_groq:
            return "openai/gpt-oss-20b", True
        if has_gemini:
            return "gemini-3.1-flash-lite", False
    if any(t in q for t in _FAST_TERMS) and has_groq:
        return "openai/gpt-oss-120b", True
    if has_gemini:
        return "gemini-3.5-flash", False
    if has_groq:
        return "openai/gpt-oss-120b", True
    return "gemini-3.5-flash", False
