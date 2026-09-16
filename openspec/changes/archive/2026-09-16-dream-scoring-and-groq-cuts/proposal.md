## Why

Dreaming burns Groq on every race with no quality feedback: shift math runs on empty form strings (auto-dreams always hit default branches), every race gets a full 20b sim regardless of leverage, and identical prompts re-pay per scan. Steal operations from OpenClaw (gated promotion, reviewable ledger) and Hermes (two-tier reasoning, idle scheduling) — adapted to our purpose (race scenarios, not memory).

## What Changes

* **Dream scoring ledger (#2 first):** every dream records favorite, odds, implied/base/Brier inputs; `settled_winners.jsonl` captures confirmed winners at settle time; daily `calibrate_dreams()` Brier-scores families (going/wind/scratch/sentiment) vs implied-only baseline. Ledger starts now, calibration compounds over 1–2 weeks.
* **Two-tier dreaming (#1):** Tier 1 deterministic keyword screen on Betfair-enriched text (free); Tier 2 Groq sims only for bet races / top-edge decile.
* **Enriched inputs (#4):** Betfair briefs + D1 recent results into dream prompts; `calculate_scenario_shift` reads combined comment text.
* **Groq batching:** 6–8 races per 120b call (JSON array schema, single fallback).
* **Prompt cache:** date-scoped prompt-hash store (volume JSON) for scan + dream paths; midnight TTL.
* **Scheduling (#3) + failover polish:** full sweep 03:00 SAST, bet-race top-ups only; instant Gemini shed on 429. (Tomorrow — needs cron/provider verification.)
* **Untouched:** decay forgetting (better than Hermes), DreamingView, DSI formula, learning engine.

## Capabilities

### New Capabilities
- `dream-scoring`: prediction ledger, winners log, family calibration.
- `groq-efficiency`: two-tier gating, batching, prompt cache, quiet scheduling.

### Modified Capabilities
- `swarm-researcher`: dream prompt inputs (Betfair briefs) — check existing spec path first; if absent, fold into dream-scoring.
