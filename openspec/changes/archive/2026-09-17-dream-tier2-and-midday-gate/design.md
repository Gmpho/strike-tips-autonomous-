## Context

Dream gating needed bet awareness the heartbeat doesn't have (it calls `generate_dream()` blind), so the decision moved inside the dreamer via `_race_has_bets` (fail-open). The midday scanner's re-buying was proven by same-day duplicate stakes, not theory.

## Goals / Non-Goals

**Goals:** Groq only where leverage exists; one pen per race per day for discovery.

**Non-Goals:** touching morning thresholds; changing DSI/decay.

## Decisions

* Tri-state `allow_llm` (None=auto) keeps heartbeat, routes, and tools untouched.
* Fail-open on lookup errors (a missed lookup must never silence a bet race).
* 8.0% midday bar is a judgment call, logged per-skip; revisit after 2 weeks of calibration data.
