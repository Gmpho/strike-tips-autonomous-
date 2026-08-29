## Context

See `proposal.md` — Why for motivation.

Current `AdaptiveOddsMonitor` builds a live snapshot from Betway global coverage every cycle and broadcasts via `set_snapshot`/SSE. Betway Timeform prose covers UK/IRE only; runners elsewhere arrive with empty commentary. The Dream heartbeat (`run_heartbeat_loop`, 5-min) already persists speculative simulations to ChromaDB; no agent fills data gaps between bets. News was polled by the same module this change introduces but is now specified separately.

## Goals / Non-Goals

**Goals:**
- Guarantee an insight for every runner in every region with zero marginal cost for the common case, plus tightly-budgeted web-grounded upgrades where they matter.
- Keep ChromaDB learning memory as the single compound memory (dreams + research + news) without duplicate writes.
- Make news linking testable by removing hidden daily-file state from the core function.

**Non-Goals:**
- Replacing Dream simulation or Bayesian calibration — additive only.
- Live odds prediction or stake sizing (handled by Governor elsewhere).
- Frontend presentation (Live Ops tab, table banners) — covered by separate changes.
- Ingesting paid data feeds or non-free RSS sources.

## Decisions

**Deterministic field blurb as default, Groq only for priority runners** — A pure-Python blurb from `form/draw/age/weight/jockey/trainer/odds` costs nothing and is always fact-safe. Gated web search + Groq is reserved for `aiSelections` + movers + `odds ≤ 6.0`, capped at 6 calls/cycle, cached per horse+date. Alternative (LLM for every runner) was rejected: at ~500 missing runners per snapshot the cost and latency are untenable.

**Region from `en` prefix + course keyword fallbacks** — The Betway `en` display prefix (e.g. `"USA: Saratoga"`) is authoritative and free; course keywords cover legacy or stripped events. Alternative (extra API for region) adds a network hop for no gain.

**Reuse Dream Groq plumbing** — `get_async_client(timeout, resolve_hosts={"api.groq.com"})` and `model="openai/gpt-oss-20b"` with `temperature 0.2 / max_tokens ~220` mirrors `_groq_insight` in `dreamer.py`. Keeps one client shape and one billing path to audit.

**xml.etree for RSS, not feedparser** — stdlib XML handles the three known feeds' `media:thumbnail/content` without adding a dependency; tolerant parsing (missing pubDate, short summary) via fallbacks.

**Freshness via Chroma search + local per-outcomeId cache** — Chroma `search_form_insights(where={type:"racing_insight", region})` plus `data/swarm_insights.json` prevents both a daily duplicate Groq call and a duplicate Chroma upsert. Alternative (rely on Groq cache alone) still writes duplicate vectors.

**Pure `_link_news_to_insights(items, seen_path?)`** — Production `poll_news()` injects the daily `news_linked_<date>.json` path; tests pass `None` and stay stateless. This was the fix for a stateful bug where a seen-file written in one test run silently blocked the next run.

**10-minute swarm interval alongside 5-minute heartbeat** — news and form gaps are lower urgency than dreams; halving the frequency halves Groq/search API QPS while still guaranteeing enrichment every monitor cycle via the inline `enrich_snapshot_with_insights` call that runs regardless of background timing.

## Risks / Trade-offs

- [RSS feed changes HTML or feed format] → parsing returns zero items; dedupe/cap still writes a valid (possibly empty) file; swarm logs `debug` and continues — *Mitigation:* three feeds (BBC/Guardian/Mirror) mean one outage does not blank the pipeline.
- [Groq rate-limit / downtime] → `_groq_call` returns `""`; runner retains field blurb; budget counter still advanced so cap is not re-tried immediately — *Mitigation:* cap is small (6) and fallbacks are safe.
- [ChromaDB unavailable] → `_fresh_insight_exists` returns `False` (skip gate disabled), `save_racing_insight` returns `False` silently; no insight is lost because `swarm_insights.json` still caches — *Mitigation:* Chroma is optional by design, mirroring existing heartbeat behavior.
- [Snapshot missing at swarm tick] → backfill no-ops for that cycle; next tick retries — *Mitigation:* inline enrichment already covers the monitor's own broadcast path.
- [Seen-file corruption] → JSON load failure returns empty set; worst case a few stories are linked twice — *Mitigation:* `save_racing_insight` upserts idempotently; duplicates dedupe in Chroma.

## Migration Plan

1. Add new data paths (`NEWS_PATH`, `SWARM_INSIGHTS_PATH`, `NEWS_IMAGES_DIR`) with auto-mkdir in `config/paths.py`.
2. Deploy `skills/swarm_researcher.py` and wire `run_swarm_loop` + `enrich_snapshot_with_insights` in `AdaptiveOddsMonitor` (guarded by `try/except ImportError` for rollback).
3. Subsequent deploys require no data migration; existing snapshots gain new runner fields (`region`, `swarmInsight`) lazily on next cycle.
4. Rollback: stop scheduling `run_swarm_loop` and omit the enrichment call — snapshot shape reverts, Chroma history remains.

## Open Questions

None — all questions that would change specs or approach were resolved during design (gate criteria, cap, purity of news linking).
