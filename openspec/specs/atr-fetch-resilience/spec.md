# atr-fetch-resilience Specification

## Purpose
Defines how the system fetches attheraces.com pages reliably from hostile
network conditions (bot mitigation, challenge shells, datacenter-IP rate
limits) without hammering the source, and how it degrades when fetching is
impossible.

## Requirements

### Requirement: Independent parser availability

HTML parsing SHALL NOT depend on fetcher imports: `Selector` is imported in
its own guarded block with a no-op fallback, so a missing browser dependency
degrades fetching tiers but never parsing code paths.

#### Scenario: Fetcher dependency missing
- **WHEN** `patchright` is absent and `scrapling.fetchers` fails to import
- **THEN** `Selector` still imports, cheap HTTP tiers still run, and no
  `NameError` escapes the parser module

### Requirement: Challenge-shell rejection

A fetched body SHALL be accepted only if it is not a challenge shell:
empty, under 8000 bytes, or a noscript-disabled stub without real content
markers (`push--x-small`, `<table>`) SHALL be rejected and the next tier
tried. The Fastly beacon script tag SHALL NEVER be used as a challenge
marker (it ships on every page).

#### Scenario: Good page with beacon accepted
- **WHEN** a 2MB results page contains the `/_fs-ch-` beacon script
- **THEN** it is accepted and parsed (beacon alone proves nothing)

#### Scenario: 3KB shell rejected
- **WHEN** a 200 response carries a 3038-byte noscript stub
- **THEN** it is rejected and the next tier is attempted

### Requirement: Cheap-first throttled tiers

Fetch order SHALL be httpx → curl-impersonation Fetcher → headless Chromium,
and the browser tier SHALL run at most once per hour per deployment (flag on
the data volume), performing a cookie-preserving reload for proof-of-work
challenges. Total fetch failure SHALL log a WARNING naming the URL.

#### Scenario: Browser throttled
- **WHEN** the browser tier ran less than an hour ago
- **THEN** it is skipped with a debug log and cheaper tiers decide the outcome

### Requirement: Cadence and budgets

Each ATR feed (results, movers, predictor) SHALL be refetched at most every
45 minutes, gated per file so a single stale feed retries alone. Fetch time
budgets SHALL be 150s per call; the monitor cron timeout SHALL accommodate
the worst case (900s). Last-good snapshots SHALL be retained and served when
all tiers fail.

#### Scenario: Single stale feed
- **WHEN** movers is 18h stale but results and predictor are 10 minutes old
- **THEN** only the movers page is fetched this cycle

#### Scenario: Total outage
- **WHEN** all tiers fail for every feed
- **THEN** existing files are kept, a staleness warning names each stale
  file with its age, and the cycle otherwise completes normally
