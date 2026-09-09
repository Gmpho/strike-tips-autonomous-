## Why

ATR results/movers/predictor snapshots went 18–55h stale twice. Two distinct
root causes: (1) `scrapling`'s fetcher import chain collapsed on Modal
because its `patchright` dependency was never installed — silently dropping
two of three fetch tiers to no-op dummies; (2) Fastly bot mitigation serves
HTTP-200 challenge shells (~3KB noscript stubs), which the fetcher accepted
as success, so empty parses skipped file writes forever while logs stayed
quiet. A 5-minute full-fetch cadence then got egress IPs rate-limited,
compounding the outage.

## What Changes

- `patchright` pinned in both `requirements.txt` and
  `pinned-requirements.txt`; Patchright Chromium pre-downloaded in
  `Dockerfile` and installed at `odds-monitor` container boot.
- `Selector` imported independently of fetchers so a fetcher-only failure can
  never kill HTML parsing again.
- Challenge-shell validation (`_is_challenge_page`): size + real-content
  markers, never the Fastly beacon script tag (present on ALL pages — using
  it as a marker caused the 18h outage by rejecting good pages).
- Cheap-first tier order (httpx → Fetcher → StealthyFetcher) with the browser
  as a throttled last resort (max 1/hour, volume-shared flag) doing a
  cookie-preserving reload for Fastly proof-of-work.
- Cadence guards: per-file 45-min freshness (`_atr_file_fresh`), so a stale
  feed retries alone without re-hammering fresh ones; `run_odds_monitor`
  timeout 600s → 900s, results/movers/predictor fetch budgets raised.
- All-tier-failure escalated from debug to WARNING with last-good retention.

## Capabilities

### New Capabilities
- `atr-fetch-resilience`: tiered fetching, challenge detection, throttling,
  and cadence policy for attheraces.com scraping.

### Modified Capabilities
(none — complements `betfair-form-data`, which covers parsing/merging.)

## Impact

- `core_agent/skills/parsers/attheraces_api.py` (tiers, validation, throttle)
- `core_agent/core/adaptive_odds_monitor.py` (cadence guards, budgets)
- `core_agent/core/modal_app.py` (900s cron timeout, 1024MB)
- `requirements.txt`, `pinned-requirements.txt`, `Dockerfile`,
  `Dockerfile.odds` (patchright packaging)
- `modal secret cloudflare-mcp` refreshed (unblocked snapshot push 401s)
- Verified: volume files fresh (movers 579, predictor 43–51, results 483–525),
  staleness warnings clear, prod views flowing.
