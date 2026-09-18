## Why

The current cloud model configurations across `core_agent/` reference invalid/deprecated model aliases (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`). When cloud providers (Groq or Gemini) are invoked—either explicitly or via the fallback chain when local Ollama is offline—requests fail with HTTP 404/400 errors or unhandled model lookup exceptions. Refactoring the cloud models establishes modern production model pools, unifies fallback routing, and eliminates all ghost aliases.

## What Changes

- Refactor `core_agent/config/model_config.py` with modern GA cloud model targets:
  - Groq: `llama-3.3-70b-versatile` (primary orchestrator / tool calling), `llama-3.1-8b-instant` (fast reads), `deepseek-r1-distill-llama-70b` (reasoning/math).
  - Gemini: `gemini-2.5-flash` (primary fast / reasoning), `gemini-2.0-flash` (fast fallback), `gemini-2.5-pro` (deep form analysis).
- Update `core_agent/agent/providers/groq.py` to use `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` instead of invalid `gpt-oss` targets.
- Update `core_agent/agents/ai_providers.py` to allow and route real production models.
- Update `core_agent/config/model_factory.py` to resolve tiers to real production models.
- Update `core_agent/config/model_registry.py`, `core_agent/skills/dreamer.py`, `core_agent/skills/swarm_researcher.py`, and `core_agent/core/strike_tips.py` to replace stale aliases with validated production models.
- Ensure `strike-tips-hud` and frontend models align cleanly with these backend cloud providers.

## Capabilities

### New Capabilities
- `cloud-models`: Contract defining cloud model pools, supported aliases, fallback cascade ordering, and error recovery policies.

### Modified Capabilities
- None.

## Impact

- **Backend Providers**: `core_agent/agent/providers/groq.py`, `core_agent/agent/providers/gemini.py`, `core_agent/agent/providers/task_router.py`.
- **Configuration & Factories**: `core_agent/config/model_config.py`, `core_agent/config/model_factory.py`, `core_agent/config/model_registry.py`.
- **Skills & Orchestrators**: `core_agent/agents/ai_providers.py`, `core_agent/skills/dreamer.py`, `core_agent/skills/swarm_researcher.py`, `core_agent/core/strike_tips.py`.
- **Frontend & HUD**: `strike-tips-hud/src/components/AIChat.tsx`, `strike-tips-hud/src/components/sidebar/SettingsView.tsx`.
