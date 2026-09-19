## 1. Central Configuration & Factories

- [x] 1.1 Update `core_agent/config/model_config.py` with standard Groq and Gemini production models
- [x] 1.2 Update `core_agent/config/model_factory.py` to map tiers to valid models
- [x] 1.3 Update `core_agent/config/model_registry.py` to register real models

## 2. Cloud Providers & Routers

- [x] 2.1 Update `core_agent/agent/providers/groq.py` to use `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`
- [x] 2.2 Update `core_agent/agent/providers/gemini.py` with production model chain
- [x] 2.3 Update `core_agent/agent/providers/task_router.py` aliases
- [x] 2.4 Update `core_agent/agents/ai_providers.py` with allowed production models

## 3. Skills & Orchestrator References

- [x] 3.1 Update `core_agent/skills/dreamer.py` and `swarm_researcher.py` model references
- [x] 3.2 Update `core_agent/core/strike_tips.py` model references

## 4. HUD Alignment & Verification

- [x] 4.1 Verify `strike-tips-hud` settings and chat selectors match cloud models
- [x] 4.2 Run linter and compiler verification
