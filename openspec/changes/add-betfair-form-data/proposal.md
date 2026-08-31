## Why

The market snapshot currently carries odds, jockey, trainer, draw and form-flag per runner — but two high-signal form fields visible on Betfair SA racecards are missing entirely: **wearing gear** (hood, tongue strap, blinkers, etc.) and **days since last run**. Gear changes and fresh/overdue horses are classic value signals that the AI analysis and the HUD dashboard cannot currently see.

Betfair SA (https://betfairsa.co.za/) publishes both fields on its racecards. This change adds Betfair SA as a lightweight form-data source alongside the existing Betway + Racing-Odds sources.

## What Changes

- Add a **new parser** `core_agent/skills/parsers/betfair_sa.py` (Betway-API pattern) that extracts, per runner, only: `gear` (normalized canonical tokens) and `daysSinceRun` (integer). No odds duplication — Betway remains the odds source of truth.
- **Merge Betfair form data into the existing market snapshot** in `AdaptiveOddsMonitor` via a new `_merge_bf_into()` (mirrors `_merge_ro_into()`), matching horses exact-first then fuzzy (`difflib`, 0.6 cutoff — same proven pattern as `_validate_value_bets`). No-match runners are skipped silently.
- **Graceful degradation + healing events**: Betfair fetch/parse failures never affect the snapshot; failures are logged via `_write_healing_event()` so the HUD Healing view shows Betfair health. If endpoint discovery forces HTML scraping, the shared `SelfHealingParser` selector rotation is used — no separate healing system.
- **HUD**: `Runner` type gains optional `gear?: string` and `daysSinceRun?: number`; RaceCard gains a sortable **Days** column and a normalized gear badge. Zero new endpoints, zero new HUD fetch loops — data rides the existing snapshot (SSE + Cloudflare KV).

## Capabilities

### New Capabilities
- `betfair-form-data`: how Betfair SA form data (gear + days since last run) is extracted, normalized, fuzzy-merged into the market snapshot, degraded gracefully with healing observability, and displayed on the HUD.

### Modified Capabilities
- None — additive fields on an additive-optional schema; existing snapshot consumers ignore unknown runner keys.

## Impact

- **Backend (new code):** `core_agent/skills/parsers/betfair_sa.py` (new ~250 lines), `core_agent/core/adaptive_odds_monitor.py` (+~60 lines: fetch + `_merge_bf_into` + healing events).
- **Contracts:** `market_snapshot` runners gain optional `gear: string` and `daysSinceRun: number` keys; `/api/ingest-snapshot` and `odds:full_snapshot` carry them transparently (no edge code change).
- **HUD (existing files, additive):** `strike-tips-hud/src/types/index.ts` (2 optional fields), `strike-tips-hud/src/components/RaceCard.tsx` (column + badge).
- **Tests (new):** parser fixture tests, merge/match tests, degradation/healing tests — hermetic, Docker-verified via plain `pytest`.
- **No schema/data migration; no Cloudflare edge change; no alert-engine change** (fresh-horse alerts are a future change).

## Non-Goals

- No Betfair odds ingestion (Betway stays the odds source of truth).
- No fresh-horse/gear-change alerting rules (future change).
- No new HUD fetch loop, KV key, or edge endpoint.
