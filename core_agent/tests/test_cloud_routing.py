"""Cloud routing validation — live-verified model IDs (Sep-2026 audit).

Groq retired llama-3.3/3.1 + deepseek (live /models list); Gemini retired
2.0/1.5-flash. A refactor shipped the dead IDs and every call 404'd into
fallback spend. These tests pin the live-verified pools and fail loudly on
regression. Static (ast/text) so they run everywhere with zero spend.
"""

import pathlib
import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]

LIVE_GROQ = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}
LIVE_GEMINI = {
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
}
# Retired/never-existed IDs that must not appear as *call targets*.
# (Backward-compat `.includes('llama')` matchers map old keys to live
# models — those use partial names and are intentionally allowed.)
DEAD_IDS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "deepseek-r1-distill-llama-70b",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "gemini-3.8-flash",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.5-transcribe",
]

CODE_GLOBS = ["core_agent/**/*.py", "strike-tips-hud/src/**/*.[tj]s*",
              "strike-tips-hud/server/*.ts"]


def _code_files():
    out = []
    for g in CODE_GLOBS:
        out.extend(REPO.glob(g))
    # Skip tests (this file defines the denylist) and caches.
    return [p for p in out
            if "__pycache__" not in str(p)
            and "/tests/" not in str(p).replace("\\", "/")]


def test_no_dead_model_ids_in_code():
    offenders = []
    for p in _code_files():
        try:
            text = p.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for dead in DEAD_IDS:
            if dead in text:
                offenders.append(f"{p.relative_to(REPO)}: {dead}")
    assert not offenders, "Dead model IDs as call targets:\n" + "\n".join(offenders)


def test_groq_models_live():
    from core_agent.agent.providers.groq import GroqProvider

    assert set(GroqProvider.MODELS) <= LIVE_GROQ, GroqProvider.MODELS
    assert "openai/gpt-oss-120b" in GroqProvider.MODELS  # flagship/tools
    assert "openai/gpt-oss-20b" in GroqProvider.MODELS  # fast reads


def test_gemini_models_live():
    from core_agent.agent.providers.gemini import GeminiProvider

    assert set(GeminiProvider.MODELS) <= LIVE_GEMINI, GeminiProvider.MODELS
    assert GeminiProvider.MODELS[0] == "gemini-2.5-flash"


def test_allowlist_and_chains_live():
    from core_agent.agents.ai_providers import AIProvider
    from core_agent.config.model_config import ModelConfig

    groq_allowed = set(AIProvider.ALLOWED_MODELS["groq"])
    gemini_allowed = set(AIProvider.ALLOWED_MODELS["gemini"])
    assert groq_allowed <= LIVE_GROQ, groq_allowed - LIVE_GROQ
    assert gemini_allowed <= LIVE_GEMINI, gemini_allowed - LIVE_GEMINI
    assert set(ModelConfig.GEMINI_CHAIN) <= LIVE_GEMINI
    assert ModelConfig.ORCHESTRATOR in LIVE_GROQ
    assert ModelConfig.GROQ_FAST in LIVE_GROQ
    assert ModelConfig.GROQ_REASONER in LIVE_GROQ


def test_router_ui_keys_present():
    text = (REPO / "core_agent/agent/providers/task_router.py").read_text()
    for key in ('"groq"', '"groq-llama"', '"gemini"', '"auto"'):
        assert key in text, f"router UI key missing: {key}"
    for dead in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                 "deepseek-r1-distill", "gemini-2.0-flash", "gemini-1.5-flash"):
        assert dead not in text, f"dead ID in router: {dead}"


def test_voice_service_models_live():
    tts = (REPO / "strike-tips-hud/server/tts-service.ts").read_text()
    assert "gemini-2.5-flash-preview-tts" in tts
    tr = (REPO / "strike-tips-hud/server/transcribe-service.ts").read_text()
    assert "whisper-large-v3" in tr  # Groq primary (live-verified)
    assert "gemini-2.5-flash" in tr  # Gemini fallback (live-verified)
    # NOTE: live-service.ts `gemini-3.8-live` is UNVERIFIED (no list endpoint
    # for Live API models) — owned by the cloud agent, tracked, not asserted.
