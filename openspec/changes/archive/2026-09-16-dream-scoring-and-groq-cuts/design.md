## Context

`_groq_insight` burns 20b/300t per race with snapshot-only context; `calculate_scenario_shift` reads `race_info["form"]` which is empty on auto-dreams (defaults) and "No recent form data." on custom ones — the keyword branches are decorative. Scan analysis is one call per race; identical prompts re-pay across morning/midday/chat.

## Goals / Non-Goals

**Goals:** measurable dream skill within 2 weeks; ~85% fewer Groq requests; Betfair-enriched dream inputs.

**Non-Goals:** changing DSI formula or decay (winning, untouched); touching learning engine internals; backfilling history.

## Decisions

* Brier scoring (not win-rate): dreams predict shifted probabilities, so proper scoring vs implied-only baseline is the honest metric. Family = keyword-derived (going/wind/scratch/sentiment/other), same sets as shift math.
* Ledger + winners log as JSONL on the volume (append-only, crash-safe, grep-able); calibration output small JSON.
* Tier 2 gate = has recorded bets OR top-edge decile (computed from the day scan, passed in — dreamer never scans itself).
* Cache key = sha256(prompt), store {response, date}; midnight scoping by file-name date + lazy purge.
* Batching applies to scan analysis calls (the volume); dream calls stay single (already 300t, batching gains little).
* Failover/scheduling verified tomorrow (needs cron + provider-path inspection, not tonight).
