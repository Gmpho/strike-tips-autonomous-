# groq-efficiency Specification

## Purpose
Cut Groq request volume to ~15% of today with zero quality loss: gate, batch, and cache.

## Requirements

### Requirement: Two-tier dream gating

Dreams SHALL run Tier 1 (deterministic keyword screen on enriched text, no LLM) for every race and Tier 2 (Groq sim) only for races with recorded bets or top-edge decile membership. Tier 1 shifts must be fully deterministic (no random fallback).

#### Scenario: Quiet race screened free
- **WHEN** a race has no bets and middling edges
- **THEN** no Groq call is made and a deterministic shift is recorded

### Requirement: Batched analysis calls

Multi-race Groq analysis SHALL pack 6–8 races per call with a JSON-array schema and SHALL fall back to single-race calls on parse failure.

#### Scenario: Batch parse fails
- **WHEN** a batched response is not valid JSON
- **THEN** each race is retried individually exactly once

### Requirement: Date-scoped prompt cache

Identical prompts SHALL be served from a volume JSON cache keyed by prompt hash, scoped to the current date (midnight TTL). Scan, dream, and rescan paths share it.

#### Scenario: Midday rescan repeats morning race
- **WHEN** the same race prompt recurs the same day
- **THEN** zero Groq calls are made and the identical JSON returns

### Requirement: Quiet scheduling and failover

Full dream sweeps SHALL run at 03:00 SAST with intraday top-ups limited to bet races; HTTP 429 SHALL shed instantly to the configured fallback model.

#### Scenario: Rate limited
- **WHEN** Groq answers 429 mid-sweep
- **THEN** remaining calls route to the fallback without failing the sweep
