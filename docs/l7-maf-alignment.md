# Implementation Plan: L7 MAF Architecture Alignment

## Objective
To align the existing `ModelPipeline` (in `ai_pydantic.py`) with the L7 resilience chain and specialized agent persona requirements specified in `GEMINI.md`.

## Key Files & Context
- `core_agent/agents/ai_pydantic.py`: Active orchestrator pipeline.
- `core_agent/prompts/analyst_agent.txt`: Expert system prompt for analysis.
- `core_agent/prompts/bankroll_agent.txt`: System prompt for bankroll management.
- `core_agent/config/model_config.py`: Contains the L7 resilience chain definitions.
- `core_agent/ollama_configs/`: Contains individual model parameters.

## Implementation Steps

### Phase 1: Persona Injection
1. Load `analyst_agent.txt` and `bankroll_agent.txt` into the pipeline.
2. Implement a `_load_system_prompt(role: str)` helper in `ModelPipeline` to read these files based on the specialist role.
3. Update `ModelPipeline._call_ollama` to use this loader to inject the correct persona into the `system` parameter.

### Phase 2: Resilience Chain Upgrade
1. Modify `ModelPipeline.chat` to ignore the hardcoded `FALLBACK_CHAIN` and instead use `ModelConfig.GEMINI_CHAIN` for the multi-tier cloud/local fallback.
2. Ensure the fallback logic handles cloud transition seamlessly if the local model fails to load (due to resource constraints).

### Phase 3: Performance Tuning (Modelfiles)
1. Standardize all `*.Modelfile` entries in `core_agent/ollama_configs/` with:
   - `PARAMETER num_ctx 2048`
   - `PARAMETER temperature 0.1`
   - `PARAMETER stop "<|eot_id|>"`
2. Regenerate these models via `ollama` CLI to ensure changes take effect.

### Phase 4: Integration
1. Remove redundant `_call_ollama` logic in `ai_providers.py` and redirect all AI calls to the new, hardened `ModelPipeline`.

## Verification & Testing
1. **Persona Test**: Chat with the bot, ask for analysis, and verify it provides JSON-structured advice using the expert persona.
2. **Resilience Test**: Simulate an Ollama model failure (e.g., stop the ollama service) and verify the system automatically falls back to the configured cloud models.
3. **Performance Test**: Confirm no "Context Canceled" errors in logs during scan due to memory management updates.
