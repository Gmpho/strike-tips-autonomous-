# cloud-models-correction Specification (delta — AMENDS refactor-cloud-models)

## Purpose

`refactor-cloud-models` SHALL-mandates IDs the providers have retired
(Groq Llama 3.3/3.1 + DeepSeek; Gemini 2.0/1.5) and labels the live IDs
invalid — the premise is inverted against the live `/models` lists
(verified Sep-2026). This delta corrects the pool; the sibling change's
proposal/spec text needs the same correction by its owner.

## Requirements

### MODIFIED Requirements

#### Cloud Model Pool Specification

The system SHALL configure and invoke only verified, production-available
cloud models. For Groq the orchestrator SHALL be `openai/gpt-oss-120b` and
the fast model SHALL be `openai/gpt-oss-20b`. For Gemini the primary SHALL
be `gemini-2.5-flash` with fallback to `gemini-2.5-flash-lite`, then
`gemini-3.5-flash`. The IDs `llama-3.3-70b-versatile`,
`llama-3.1-8b-instant`, `deepseek-r1-distill-llama-70b`, `gemini-2.0-flash`,
and `gemini-1.5-flash` SHALL NOT appear as call targets anywhere in code.

- **WHEN** any code change introduces a cloud model ID
- **THEN** `test_cloud_routing.py` SHALL fail the build unless the ID is in
  the live-verified pool above.

### ADDED Requirements

#### TPM budget

Per-race value prompts SHALL stay under ~1500 estimated tokens via the slim
projection (track/number/distance/condition + ≤14 runners ×
horse/odds/form/jockey/trainer). HTTP 413 SHALL surface immediately (no
retry); 429 SHALL retry at most once.
