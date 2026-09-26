## Purpose

Establish the formal behavioral and configuration contract for cloud LLM providers (Groq and Gemini) across the Strike Tips racing intelligence platform, defining valid model aliases, tier mapping, fallback sequences, and tool calling schemas.

## Requirements

### ADDED Requirements

#### Cloud Model Pool Specification
The system SHALL configure and invoke only verified, production-available cloud models. For Groq, the orchestrator model SHALL be `llama-3.3-70b-versatile`, the fast lightweight model SHALL be `llama-3.1-8b-instant`, and the reasoning model SHALL be `deepseek-r1-distill-llama-70b`. For Gemini, the primary model SHALL be `gemini-2.5-flash` with fallback to `gemini-2.0-flash`.

#### Scenario: Groq Request Dispatch
- GIVEN a request routed to the Groq provider
- WHEN the request requires tool calling or deep analysis
- THEN the system SHALL dispatch using `llama-3.3-70b-versatile`
- AND WHEN the request requires only fast text completion without tools
- THEN the system SHALL dispatch using `llama-3.1-8b-instant`.

#### Scenario: Gemini Fallback Sequence
- GIVEN a cloud fallback or direct Gemini dispatch
- WHEN attempting model generation
- THEN the system SHALL iterate through `["gemini-2.5-flash", "gemini-2.0-flash"]`
- AND if a 429 or rate limit occurs, retry with exponential backoff before advancing to the next model.

#### Tier Resolution and Factory Mapping
The model factory SHALL resolve logical tiers (`ORCHESTRATOR`, `PARALLEL`, `CLOUD_FALLBACK`) strictly to production models:
- `ORCHESTRATOR` -> Groq `llama-3.3-70b-versatile` (or Gemini `gemini-2.5-flash` if Groq key is absent).
- `PARALLEL` -> Gemini `gemini-2.5-flash`.
- `CLOUD_FALLBACK` -> Gemini `gemini-2.5-flash`.

#### Scenario: Missing API Key Handling
- GIVEN a request requiring a cloud provider
- WHEN the requested provider's API key is absent from the environment
- THEN the provider SHALL raise a descriptive ValueError or gracefully fall back to an available provider without crashing the process.
