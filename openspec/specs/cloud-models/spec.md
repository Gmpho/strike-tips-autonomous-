# cloud-models Specification

## Purpose
Establishes the formal behavioural and configuration contract for cloud LLM providers (Groq and Gemini) across the Strike Tips racing intelligence platform: the authoritative live-verified model pool, tier mapping, fallback sequencing, token budgets, and the rule that this capability is the single source of truth for model identifiers.

> **Authoritative pool — verified against the providers' live `/models` endpoints on 2026-09-19.** This capability is the single source of truth: provider routing code, cloud-model documentation, and any model warm-up script SHALL agree with the list below. Re-verify before changing it.
>
> Corrections folded in here from the previously separate `cloud-models-correction`
> capability (one concern, one capability): the pool now names the live IDs, the
> Gemini chain is `2.5-flash → 2.5-flash-lite → 3.5-flash`, and the TPM budget
> requirement lives here.

## Requirements

### Requirement: Cloud Model Pool Specification
The system SHALL configure and invoke only verified, production-available cloud models. For Groq the orchestrator SHALL be `openai/gpt-oss-120b` and the fast model SHALL be `openai/gpt-oss-20b`. For Gemini the primary SHALL be `gemini-2.5-flash` with fallback to `gemini-2.5-flash-lite`, then `gemini-3.5-flash`. The IDs `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `deepseek-r1-distill-llama-70b`, `gemini-2.0-flash`, and `gemini-1.5-flash` SHALL NOT appear as call targets anywhere in code.

#### Scenario: Groq request dispatch
- **WHEN** a request routed to the Groq provider requires tool calling or deep analysis
- **THEN** the system SHALL dispatch using `openai/gpt-oss-120b`
- **AND WHEN** the request requires only fast text completion without tools
- **THEN** the system SHALL dispatch using `openai/gpt-oss-20b`

#### Scenario: Gemini fallback sequence
- **WHEN** a cloud fallback or direct Gemini dispatch attempts model generation
- **THEN** the system SHALL iterate through `["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash"]`
- **AND** if a 429 or rate limit occurs, the system SHALL retry with exponential backoff before advancing to the next model

#### Scenario: Retired model ID fails the build
- **WHEN** any code change introduces a cloud model ID
- **THEN** `test_cloud_routing.py` SHALL fail the build unless the ID is in the live-verified pool above

### Requirement: Tier Resolution and Factory Mapping
The model factory SHALL resolve logical tiers (`ORCHESTRATOR`, `PARALLEL`, `CLOUD_FALLBACK`) strictly to live-verified models:
- `ORCHESTRATOR` -> Groq `openai/gpt-oss-120b` (or Gemini `gemini-2.5-flash` if the Groq key is absent).
- `PARALLEL` -> Gemini `gemini-2.5-flash`.
- `CLOUD_FALLBACK` -> Gemini `gemini-2.5-flash`.

#### Scenario: Missing API key handling
- **GIVEN** a request requiring a cloud provider
- **WHEN** the requested provider's API key is absent from the environment
- **THEN** the provider SHALL raise a descriptive ValueError or gracefully fall back to an available provider without crashing the process

### Requirement: Live-verified model inventory
The pool SHALL be verified against the providers' `/models` endpoints and the capability SHALL record the verification date. An identifier that cannot be verified because its API exposes no enumeration endpoint SHALL be recorded as explicitly unverified and SHALL NOT be cited as authoritative. `gemini-3.8-live` (Live API) is currently unverified on this basis.

#### Scenario: Unverifiable identifier is marked, not assumed
- **WHEN** a model identifier cannot be confirmed against a provider enumeration endpoint
- **THEN** the capability SHALL mark it explicitly unverified rather than presenting it as authoritative

#### Scenario: Pool drifts from the providers
- **WHEN** a re-probe shows a listed model no longer exists, or shows a retired model still referenced in code
- **THEN** the pool and the offending reference SHALL both be corrected before the change is accepted

### Requirement: TPM budget
Per-race value prompts SHALL stay under ~1500 estimated tokens via the slim projection (track/number/distance/condition + ≤14 runners × horse/odds/form/jockey/trainer). HTTP 413 SHALL surface immediately (no retry); 429 SHALL retry at most once.

#### Scenario: Oversized prompt surfaces instead of retrying
- **WHEN** a per-race value prompt exceeds the estimated token budget, or the provider returns HTTP 413
- **THEN** the request SHALL surface immediately with no retry, and an HTTP 429 SHALL retry at most once
