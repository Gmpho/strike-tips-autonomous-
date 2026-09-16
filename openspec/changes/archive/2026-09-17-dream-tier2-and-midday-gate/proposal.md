## Why

Follow-up to dream-scoring-and-groq-cuts: auto Tier selection (no caller changes), Betfair briefs on the `/dream` path, and a betting gate on the continuous scanner (which re-buys races all day on nondeterministic AI rolls — the structural source of the longshot bleed).

## What Changes

* `generate_dream(allow_llm=None)`: auto Tier-2 for races with open tickets, Tier-1 otherwise; explicit True/False override.
* Custom dreams (`/dream` command) get Betfair briefs + enriched shift math.
* Midday continuous scan: skip races holding a same-day PENDING ticket; edge bar 5.5% → 8.0%.
* Morning scan remains the sole discovery path.

## Capabilities

### New Capabilities
- (none — extends dream-scoring + groq-efficiency)

### Modified Capabilities
- `dream-scoring`: auto tier selection, custom-path enrichment.
- `groq-efficiency`: midday betting gate.
