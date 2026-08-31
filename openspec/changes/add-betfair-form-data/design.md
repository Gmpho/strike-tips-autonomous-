## Context

The market snapshot pipeline is already a multi-source merge bus: `BetwayAPI.get_snapshot_format()` produces the flat `market_snapshot` schema, `AdaptiveOddsMonitor` merges Racing-Odds into it via `_merge_ro_into()`, enriches it, caches it, and pushes it to Cloudflare KV via `POST /api/ingest-snapshot` (TTL 300s). The HUD consumes it over SSE/REST — no HUD-side fetch logic per source. Two form fields visible on Betfair SA racecards (wearing gear, days since last run) are absent everywhere in the codebase.

betfairsa.co.za is a JavaScript SPA (4 KB HTML shell, no endpoints in static HTML). Discovery (task 1.1) was completed via Chrome DevTools MCP network capture and confirmed a **clean JSON API** — no HTML scraping or PDF fallback is required.

## Discovered API (base: `https://exchange.betfairsa.co.za/customer/`)

| Purpose | Endpoint | Returns |
|---|---|---|
| Sports list | `GET /api/sports` | Horse Racing = sport id `"7"` |
| Regional groups | `GET /api/sports/7` | GROUP nodes with `countryCode` (RSA = `"ZA"`, group id `1549417158`) |
| Race headers | `GET /api/horse-racing/7/all?timeRange=TODAY\|TOMORROW\|WEEK` | wallet groups → events → markets (marketId e.g. `1.261661770`) |
| **Runner details (TARGET)** | `GET /api/market/{marketId}` | `runners[]` with `metadata.wearing` + `metadata.days_since_last_run` |

### Runner detail shape (`/api/market/{marketId}` → `runners[].metadata`)

```json
{
  "runnername": "Task Force",
  "selectionid": 9377621,
  "metadata": {
    "wearing": "blinkers and tongue strap",
    "days_since_last_run": "16",
    "jockey_name": "Qiniso Ngcobo",
    "trainer_name": "D. W. Moore",
    "form": "564-628",
    "weight_value": "132.0",
    "age": "4",
    "cloth_number": "1",
    "stall_draw": "1"
  }
}
```

**Parser extracts:** `gear` ← `metadata.wearing`, `daysSinceRun` ← `int(metadata.days_since_last_run or 0)`, match key ← `runnername`. The endpoint is public-readable (HTTP 200 without auth cookies) and returns pure JSON — the Betway pattern applies directly.

## Goals / Non-Goals

**Goals:**
- Get `gear` + `daysSinceRun` onto every snapshot runner the HUD shows, via Betfair SA.
- Keep Betway as the sole odds source of truth; Betfair contributes form fields only.
- Degrade gracefully: Betfair problems never touch snapshot availability (same contract as the Racing-Odds merge).
- Reuse existing infrastructure end-to-end: snapshot bus, Cloudflare KV, healing-event log, `difflib` matching pattern, `SelfHealingParser` (only if HTML scraping is required).

**Non-Goals:**
- Betfair odds ingestion, exchange prices, or volume data.
- Alerting on fresh horses / gear changes (future change).
- New HUD fetch loops, KV keys, or edge endpoints.

## Decisions

- **Merge into the existing snapshot; no separate HUD JSON.** The snapshot is already the multi-source bus (`_merge_ro_into` precedent). A separate `betfair.json` would add a second poll loop, a second KV key, a second data-bridge fetch, and a second staleness story for two small fields. Runners gain two optional keys; all existing consumers ignore unknown runner keys.
- **Separate parser module** `parsers/betfair_sa.py`, mirroring `betway_api.py` structure. It returns the *minimal* form shape (name/gear/daysSinceRun only) so source responsibilities stay clean at code level even though the data merges at snapshot level. Raw responses cached to `data/betfair_form_*.json` for debugging.
- **Exact-first, then fuzzy (0.6), then skip.** Horse-name matching across bookmakers must handle `(IRE)` suffixes, spacing, punctuation and minor drift; `difflib.get_close_matches(..., cutoff=0.6)` is the codebase's proven pattern (`_validate_value_bets`). A wrong-horse attach is worse than absent data, so unmatched runners are skipped, never guessed.
- **Gear normalization at parse time, not render time.** Canonical token set (`Hood`, `Blinkers`, `Tongue strap`, `Visor`, `Eye shade`, `Cheek pieces`, `Cross noseband`, `Rear looker`), `·`-joined, so the HUD badge stays dumb and future alerting can match tokens deterministically. Unrecognized gear text passes through title-cased rather than dropped.
- **Healing via existing mechanisms only.** Failures/skips → `_write_healing_event()` (HUD Healing view). If discovery forces HTML scraping → shared `SelfHealingParser` selector rotation for the betfair fields. No new healing subsystem.
- **Fetch cadence:** Betfair form data is slow-moving (gear/last-run don't change intra-race), so it is fetched on the monitor's slow cycle and cached to disk; a failed cycle reuses the last good form cache (max-age bounded) before giving up for that cycle.

## Risks / Trade-offs

- **SPA endpoint fragility (RESOLVED in discovery).** The highest risk — that Betfair SA endpoints would be obfuscated, session-gated, or bot-protected — is resolved: `/api/market/{marketId}` is public-readable (HTTP 200, no auth cookies) and returns pure JSON. The Betway `httpx` pattern applies directly; no HTML scraping or PDF fallback is needed. The PDF Computaform source (`pdf_harvester.py`) remains a documented Plan-B only if the endpoint is ever deprecated.
- **Fuzzy false positives.** Two different horses with similar names (e.g. `"Silver Storm"` vs `"Storm Chaser"`) could cross 0.6. Mitigation: match within a single (track, race) scope only, prefer highest-score candidate, and exclude already-matched Betfair runners from the candidate pool (one-to-one assignment).
- **Snapshot payload growth.** Two small fields per runner (~40 bytes/runner) is negligible against the 300s-KV TTL budget.
- **Codifying thresholds.** The 0.6 cutoff and canonical token set become contract; changing them later is a MODIFIED spec via the normal change flow.
