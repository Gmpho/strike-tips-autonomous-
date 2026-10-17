# Exotic supersede, scan provenance, and partial-feed leg safety

## Why

On Friday 2026-10-16 (Fairview) the bot placed two tickets on the *same* pool
from two different scans:

| scan | pool | result |
|------|------|--------|
| 05:00 daily (`03:07Z`) | Bipot, Place Accumulator | **LOST** |
| 09:30 value (`07:35Z`) | Bipot, Place Accumulator | **WON** (R1,254.24 + R2,073.96) |

The one-per-pool-per-day rule was **first-wins**, so the 05:00 losing tickets
blocked the 09:30 winners. Fairview's net was **+R3,286.34**; under first-wins
it would have been **-R41.86** — a R3,328 swing on one day's paper bankroll.

Two related defects surfaced the same night:

1. **False dead leg.** A place-pool leg was failed because the results feed
   listed the winner but no 2nd/3rd, so the ticket's candidates matched rows
   with *blank* placings and blank was read as "ran and missed". This buried
   the official 6/6 Fairview Bipot as LOST (manually repaired).
2. **Unprovable verdicts.** The LOST note said only "dead leg", with no record
   of which leg or what placings the data carried — and Modal log retention is
   minutes, so the evidence was gone within the hour.

## What changes

- **(b) Supersede.** A later scan may replace an earlier ticket for the same
  pool **only while it is still PENDING, in the same paper/real mode, and
  before any leg has started**. Superseded tickets become VOID (outside the
  duplicate key), are refunded, and the replacement is recorded. Settled
  tickets are never touched.
- **(i) Scan provenance.** Each exotic ticket records `source` (`daily` /
  `value`) in its notes JSON, so "which scan picked X" is answerable.
- **(ii) Partial-feed safety.** A place leg dies only when the required
  placings are all present; otherwise it holds. A listed runner with no
  published placing is missing data, not a loss — in multi-leg and
  single-race (Exacta/Trifecta/Quartet) pools alike.
- **Forensic notes.** LOST verdicts name the dead legs and each candidate's
  confirmed placing.

## Impact

- `core_agent/skills/bankroll_manager/governor.py` (duplicate handling, notes)
- `core_agent/core/strike_tips.py` (source resolution, supersede guard)
- `core_agent/skills/result_tracker.py` (leg verdicts, LOST notes)
- Ledger: supersede adds VOID rows; no schema change.

## Out of scope

- Cross-pool conflicts, real-money supersede policy, per-track off-time tables
  (the guard reads race times from the scan's own race data).
