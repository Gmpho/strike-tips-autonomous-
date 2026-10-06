# Capability: hardening-post-review

## Purpose

Close the five verified defects without altering any other behavior.

## ADDED Requirements

### Requirement: Failed parses never poison writes

A malformed ledger file SHALL load as a flagged error state, and no save
SHALL persist that state over the previous good data.

#### Scenario: Corrupt history file
- **WHEN** `bet_history.json` fails to parse
- **THEN** in-memory bets stay empty AND flagged corrupt AND the next
  `_save_state` refuses to write, preserving the file for repair

### Requirement: Inbound auth on /v1 proxy

The Pages `/v1/*` proxy SHALL reject requests without a valid caller key
before proxying, matching its own header comment.

#### Scenario: Anonymous inference attempt
- **WHEN** POST /v1/chat/completions arrives with no key or session
- **THEN** 401, no upstream call, no model spend

### Requirement: Bounded winner extraction

Pattern 5 SHALL be sentence-bounded like patterns 1–4, and fuzzy-scrape
wins SHALL report confidence below 1.0.

#### Scenario: Horse name far from result token
- **WHEN** a candidate name and "1st" appear in different sentences
- **THEN** no match from pattern 5; structured placing remains primary

### Requirement: Honest DSI

DSI SHALL use Bayesian smoothing (Beta prior) with a minimum-evidence floor,
and non-qualifying reads SHALL be labeled heuristic, not Bayesian.

#### Scenario: Three dreams, one negative
- **WHEN** only 3 dreams exist with 1 negative
- **THEN** the smoothed estimate stays near the prior (no ×0.50 swing)

### Requirement: Continuous reconciliation

A scheduled reconciliation SHALL compare JSON vs Postgres ledger totals and
alert on Telegram on any drift.

#### Scenario: Post-import settlement
- **WHEN** a bet settles after the import
- **THEN** the next reconcile flags the ledgers as diverged until dual-write
  lands (expected), rather than silently drifting
