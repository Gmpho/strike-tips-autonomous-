# Implementation Plan: Decoupled System Grounding

## Objective
Decouple the "Grounding Logic" from the `AIProvider` and `ModelPipeline` to maintain a clean, specialized `GroundingEngine` in `core_agent/core/`. This keeps the Pydantic-orchestrator focused on intent and tool dispatch, while the `GroundingEngine` manages real-time context.

## Key Changes
1. **New Service**: `core_agent/core/grounding_engine.py` - A dedicated service that orchestrates `search_racing_data` and `PDFHarvester` before feeding context to the AI.
2. **Refactor**: Remove grounding logic from `AIProvider` and `StrikeTips`.
3. **Integration**: `ModelPipeline` will now call `GroundingEngine` as a middleware step.

## Implementation Steps

### Phase 1: Create Grounding Engine
1. Create `core_agent/core/grounding_engine.py`.
2. Move logic from `AIProvider._get_search_context` and `PDFHarvester` calls into this class.
3. Include an "Autonomous Loop": if search results are empty, try 2 fallback query variations automatically.

### Phase 2: Orchestration Middleware
1. Update `core_agent/agents/ai_pydantic.py` to call `GroundingEngine` before any LLM prompt is constructed.
2. The orchestrator remains clean: it just gets the "Context String" from the engine and injects it into the prompt.

### Phase 3: Cleanup
1. Deprecate the old grounding methods in `ai_providers.py` and `strike_tips.py`.
2. Ensure the new engine is used by both the daily scan and the interactive chat orchestrator.

## Verification
1. **Pydantic Purity**: Verify `ai_pydantic.py` no longer contains search or PDF logic.
2. **Grounding Trace**: Verify logs show `[GROUNDING] Engine: Initialized` and `[GROUNDING] Context injected` before model calls.
3. **No-Silence Test**: Verify that the daily scan calls the `GroundingEngine` first to check for "hidden" racing data if the API is empty.

## Rollback Plan
- Restore the `ai_providers.py` search context logic if the middleware adds unacceptable latency.
