## Why

Betway publishes rich Timeform prose for UK/IRE only — roughly half of each day's card (e.g. USA, Japan, South Africa runners) arrives with `timeForm=""` and no star rating. Operators have no analytical commentary for those regions. An autonomous backfill that guarantees an insight for every runner, at zero marginal cost plus tightly-gated AI upgrades for priority selections, is needed alongside the existing Dream heartbeat.

## What Changes

- New background agent `core_agent/skills/swarm_researcher.py` run as second loop (`run_swarm_loop`, 10-min interval) alongside `run_heartbeat_loop` in `AdaptiveOddsMonitor`.
- **Phase A — Form backfill:** detection of runners missing `timeForm`; region detection from Betway `en` prefix with course-keyword fallbacks (USA, Japan, South Africa, UK/IRE, Australia, New Zealand, France, Hong Kong, UAE); deterministic zero-cost field blurb (`form, draw, age/weight, jockey, trainer, odds`) for every missing runner; gated web-grounded Groq summary for priority runners only (`aiSelections` + market movers + odds ≤ 6.0, cap 6 calls/cycle, per-horse+day cache).
- **RSS news ingestion:** free BBC Sport / Guardian / Mirror feeds polled every 10 min, XML parsed, deduped by link, capped at 50, atomically written to `data/news_latest.json`.
- **News → ChromaDB linking:** pure function `_link_news_to_insights(items, seen_path?)` stores verbatim news when headline/summary names a live snapshot horse or course; production caller passes daily `news_linked_<date>.json` path, tests stay stateless.
- **Snapshot enrichment:** `enrich_snapshot_with_insights(state)` injects `region / swarmInsight / insightSource` onto each runner before `set_snapshot`/SSE push; reads warm `data/swarm_insights.json` cache (per-outcomeId) and generates field blurbs live.
- **Persistence:** `save_racing_insight()` central writer into ChromaDB `form_insights` (`type:"racing_insight"`) plus `curated_memory.append_agent_note`; `data/swarm_insights.json` per-outcomeId cache.
- New data paths `NEWS_PATH`, `NEWS_IMAGES_DIR`, `SWARM_INSIGHTS_PATH` in `config/paths.py`.
- News REST (`GET /api/news`, `GET /api/news/images`) and SSE `event: news` already covered separately; this change adds the poller backing them.

## Capabilities

### New Capabilities
- `swarm-researcher`: Autonomous all-region form insight backfill and RSS news ingestion — scheduling, region detection, deterministic blurbs, gated AI upgrades, deduplication, snapshot enrichment, and ChromaDB persistence. Each behavior becomes a SHALL requirement in this capability's spec.

### Modified Capabilities
<!-- No existing spec requirements change; swarm is additive. -->

## Impact

- **Backend:** `adaptive_odds_monitor.py` (new loop + enrichment hook), `config/paths.py` (new constants), `heartbeat`/`dream` unchanged, ChromaDB load (+`racing_insight` documents), Groq spend tightly capped, disk writes (`news_latest.json`, `swarm_insights.json`, `news_linked_<date>.json`, `data/dsi_cache.json` for DSI only).
- **Frontend:** consumers read enriched snapshot fields (`region`, `swarmInsight`); no frontend changes in this capability (covered by Live Ops / table UX changes separately).
- **Tests:** pure functions + cap/freshness/budget invariants are unit-testable without network.
