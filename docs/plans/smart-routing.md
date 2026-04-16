# Plan: Smart Model Routing & Selection

## Objectives
1. **Intent Classifier Upgrade**: Expand regex patterns in `IntentClassifier` for more natural language support.
2. **LLM-Based Router**: Add a fallback intent classifier using `racing_llama` when regex fails.
3. **Frontend API & UI**: Ensure model selection propagates through the API and add a UI dropdown for control.

## Implementation Steps
### 1. Backend: Intent Classifier (`core_agent/agents/intent_classifier.py`)
- Expand regex patterns for common racing queries.
- Add `classify_with_llm` method using `racing_llama` as a fallback.

### 2. Backend: AI Orchestration (`core_agent/agents/ai_pydantic.py`)
- Update `ModelPipeline` to use the new intent classifier before model routing.

### 3. Frontend: API & UI (`strike-tips-frontend/`)
- Update `api.ts` to include `model` in the `chatWithAgent` request.
- Update `page.tsx` to expose the new model dropdown to the chat interface.

## Verification
- Test natural language queries with "unknown" intents.
- Verify that selected models from the dropdown are correctly passed to the backend.
