# Capability: composio-creation-tools

## ADDED Requirements

### Requirement: Subscriber account connection
The system SHALL let a subscriber connect their own Google/X account via a
Composio Connect Link issued from Telegram (`/connect x|google`), keyed by
Telegram chat ID; revoking SHALL only delete the mapping.

#### Scenario: Connect Google
- WHEN the subscriber taps `/connect google` and completes OAuth
- THEN a subsequent `create_analysis_sheet` call executes under their
  connection and the sheet appears in their Drive.

### Requirement: Fixed internal tool surface
The agent SHALL expose exactly `create_analysis_sheet`,
`export_pnl_report`, and `publish_tip_post` with fixed schemas; vendor
tool slugs SHALL NOT appear in model-facing schemas or prompts.

#### Scenario: Registry audit
- WHEN listing `TOOL_REGISTRY` entries visible to models
- THEN no entry name contains a vendor prefix and each maps to the
  adapter, not Composio directly.

### Requirement: Deterministic numbers
PnL figures SHALL be computed in Python from `bet_history.json` +
`bankroll_state.json` before any model or Composio involvement; models
MAY add prose around injected facts but SHALL NOT generate figures.

#### Scenario: PnL export audit
- WHEN exporting a weekly report
- THEN every figure in the sheet matches ledger recomputation exactly.

### Requirement: Spend-bounded posting
X posts SHALL be link-free by default ($0.015); URL posts require explicit
user opt-in; a per-user daily cap SHALL block excess with a friendly
message; HTTP 402 SHALL pause posting and raise a spending alarm.

#### Scenario: Cap exceeded
- WHEN a subscriber over the daily cap requests another post
- THEN no post is created and the reply states the cap and reset time.

### Requirement: Graceful fallback
Any Composio/Google/X failure SHALL return content via Telegram + Email
instead, with the error named plainly; no silent drops.

#### Scenario: Revoked token
- WHEN a call fails with revoked/expired auth
- THEN the subscriber gets a re-link prompt, not a traceback.
