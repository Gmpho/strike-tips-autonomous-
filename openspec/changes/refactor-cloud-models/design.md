# Design: Refactor Cloud Models

## Context
The repository utilizes a multi-model architecture where local Ollama models serve as sovereign local agents, with Groq and Gemini as cloud providers. Over time, fictional model aliases (`gpt-oss-120b`, `gemini-3.5-flash`) were introduced into configuration files, resulting in runtime failures whenever cloud inference was triggered.

## Goals
1. Standardize on stable, production-supported models for Groq and Gemini across all backend services.
2. Eliminate all occurrences of deprecated/invalid model names.
3. Ensure automatic and seamless fallback: Local Ollama -> Groq (`llama-3.3-70b-versatile`) -> Gemini (`gemini-2.5-flash`).
4. Keep the HUD frontend options in sync with the backend provider choices.

## Decisions

1. **Groq Model Selection**:
   - `llama-3.3-70b-versatile` as the flagship Groq model for complex racing analysis, orchestration, and function calling.
   - `llama-3.1-8b-instant` for ultra-fast, tool-free summary generation.
   - `deepseek-r1-distill-llama-70b` for deep math/probability edge calculations.

2. **Gemini Model Selection**:
   - `gemini-2.5-flash` as primary workhorse for Google AI Cloud.
   - `gemini-2.0-flash` as rapid fallback.
   - `gemini-2.5-pro` as optional deep race card evaluator.

3. **Unified Model Resolution in Factory**:
   - `core_agent/config/model_factory.py` maps `ORCHESTRATOR` to `llama-3.3-70b-versatile` if `GROQ_API_KEY` is present, or defaults to `gemini-2.5-flash`.
