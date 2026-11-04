# Tasks

## 1. Governor — supersede + provenance

- [x] 1.1 Add `supersede: bool = False, source: str = ""` to `record_exotic_bet`
- [x] 1.2 Supersede branch: when a duplicate exists, is PENDING, and matches
      paper/real mode — set `VOID`, note `| VOID (superseded by <source>)`,
      refund stake (paper → `paper_balance`; real → bankroll + P/L), continue
- [x] 1.3 Otherwise keep first-wins skip (`return None`), unchanged
- [x] 1.4 Persist `source` in the ticket notes JSON
- [x] 1.5 Mutate directly inside the existing `_atomic_transaction` (not
      re-entrant; `void_settlement` returns to PENDING, so not usable)

## 2. Scan provenance and supersede guard

- [x] 2.1 `run_daily_scan(..., source: Optional[str] = None)`
- [x] 2.2 Resolve `source` when unset: SAST hour < 8 → `daily`, else `value`
      (both Modal crons run the same CLI, so hour is the discriminator)
- [x] 2.3 `_meeting_started(track, legs)`: True if any leg's off time is past
      or unreadable → supersede refused
- [x] 2.4 Pass `supersede=not _meeting_started(...)` and `source=` to
      `record_exotic_bet`

## 3. Partial-feed leg safety

- [x] 3.1 Multi-leg: fail only when `requirement ⊆ confirmed placings`, else
      hold `unknown` (guard placed *after* the early pass loop)
- [x] 3.2 Single-race: a listed runner with a blank placing returns unknown,
      not a fail
- [x] 3.3 LOST notes name dead leg races + each candidate's confirmed placing

## 4. Tests

- [x] 4.1 Partial place feed does not kill a live leg
- [x] 4.2 Place leg still dies when placings are complete
- [x] 4.3 LOST note names the dead leg and evidence
- [x] 4.4 Blank single-race banker holds (PENDING), not LOST
- [x] 4.5 Later scan supersedes a pending ticket
- [x] 4.6 Supersede never touches a settled ticket
- [x] 4.7 Default remains first-wins
- [x] 4.8 Source recorded in ticket notes
- [x] 4.9 Full suite: 526 passed, 2 pre-existing failures, 4 pre-existing
      `fastapi` collection errors (baseline 521 → +5 new, no regressions)

## 5. Ship

- [x] 5.1 `compile()` check on every edited file
- [x] 5.2 Commit + push
- [x] 5.3 `modal deploy core_agent/core/modal_app.py` (~04:23 SAST 2026-10-17, before the 05:00 daily scan)
- [x] 5.4 Post-deploy: `/api/betting/history` returns data
