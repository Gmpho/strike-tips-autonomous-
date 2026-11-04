# Design

## Supersede vs. first-wins

The existing rule (kept earliest, cancelled the rest) is safe against
double-spend but assumes the earliest ticket is the best one. In practice two
scans run hours apart — 05:00 daily (thin form, racecard only) and 09:30 value
(odds + Beta + form) — so the *later* pick is the better-informed one. On
2026-10-16 the daily picks lost and the value picks won the same pools.

A blind "last wins" is unsafe: it could replace a live winner whose races
have already run but not yet settled. So supersede is gated on three
conditions, all cheap to check at record time:

1. `existing.status == "PENDING"` — settled money is final
2. `existing.is_paper == is_paper` — never mix paper and real ledgers
3. the meeting has not started — no leg's off time is in the past

Condition 3 fails *closed*: an unreadable off time is treated as "started",
because failing to supersede costs a duplicate (recoverable) whereas
wrongly superseding costs a winner (not recoverable).

## Why VOID and not PENDING

`void_settlement` returns a ticket to PENDING, so it would still occupy the
duplicate key and block the replacement. The duplicate guard tests
`status in ("PENDING", "WON", "LOST")`, so setting VOID removes the old
ticket from the key set while keeping it in the ledger as an audit row.

## Why mutate inside the existing transaction

`_atomic_transaction` reloads state on entry, so a nested call would operate
on a *second* copy of the state and the outer `commit()` would clobber it.
The supersede mutation therefore happens inline in the same transaction that
records the replacement.

## Source discrimination

Both Modal crons (`daily_scan` 05:00, `value_scan` 09:30 SAST) invoke the same
CLI (`python3 core_agent/core/strike_tips.py scan`), so the entry point cannot
tell them apart. Rather than touching `modal_app.py` (protected, and shared
timeouts/crons), the source is derived from the scan's start hour: < 08:00
SAST → `daily`, otherwise `value`. The in-app APScheduler path (`scheduler.py`)
defaults to `daily`, consistent with its own naming. An explicit `source=`
argument always wins.

## Partial-feed safety

The original fail path asked "does any candidate row show a placing the pool
requires?" — and treated a blank placing as a loss. ATR publishes the winner
before the remainder of the field, so a place leg could die on a feed that was
merely young. The guard inverts the test: a leg dies only when the *required*
placings are all confirmed in the data. The same reasoning applies to
single-race pools (Exacta/Trifecta/Quartet), where a listed banker with no
placing is unpublished, not beaten — matching the function's own contract that
missing place data stays unknown and is never guessed.

## Trade-offs

- Supersede adds VOID rows for audit; the ledger grows by one row per
  superseded ticket. Accepted: it is the only way to keep the money trail.
- Supersede is refused once a meeting starts, so if the value scan is delayed
  past the first off it will duplicate rather than replace. Safest failure
  direction.
- The hour-based source heuristic mislabels a manual rescan. Acceptable until
  a scan is invoked with an explicit `source`.
