# Proposal: Exotic Settlement Observability

## Why
`_settle_exotic_ticket` declines to settle a pool ticket from six different
branches, and every one of them was a bare `return None`. The ledger showed a
stale ticket; the reason lived only in container logs that rotate away. That is
why the backlog looked like "exotics never settle" when in fact the causes are
distinct: expired age, unparseable legs, no day-scoped results, final leg not
run, indeterminate placings, or a missing tote dividend.

The dividend machinery already exists (`_extract_pool_dividend`,
`_parse_raceform_dividend` via Raceform's archive JSON, and
`admin_tasks.py:417` for a manual official-dividend correction). What was
missing is knowing which branch fires and how often.

## What changes
- New `core_agent/skills/settlement_diagnostics.py`:
  - `record_pending(bet_id, reason, detail, track, pool_type)` → INFO log +
    append to `DATA_DIR/settlement_diagnostics.jsonl` (rotates at 1MB, keeps
    one `.1` backup).
  - `recent(limit)` / `latest_by_bet()` for ops reads.
  - Reasons are a closed set: `age_expired`, `unparseable`, `no_results`,
    `before_off_time`, `unknown_legs`, `no_dividend`, `settle_failed`.
- `result_tracker.py`: the seven decline points now call `_record_pending(...)`
  before returning. **No settlement logic, maths, or status changes.**

## Non-goals
- No automatic dividend discovery. If `no_dividend` dominates after two weeks,
  that is the signal to hunt the tote dividend feed (REA/HAR session).
- No ledger/void behaviour change; `record_pending` is write-only observation
  and swallows OSError so a read-only volume can never block settlement.

## Verification
`tests/test_settlement_diagnostics.py` (7 tests) + existing exotic settlement
suites re-run: 68 passed, settlement chain 50 passed / 2 skipped.
