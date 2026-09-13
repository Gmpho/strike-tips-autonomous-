## Why

Two live-money defects on Sep 12-13: (1) exotic tickets never settled (skipped by design, dividend path never built) — then the first leg-settler scored Sep-10/11 tickets against Sep-12 results (ATR serves today/yesterday only) and recorded same-day duplicates 4×; (2) Thursday's Vaal card harvested on Sunday went out as "turffontein" (first-dict-key label) and took a real R9.60 ticket.

## What Changes

* Leg-based exotic settlement: banker-or-saver vs ATR placed results (PA top-3, Bipot top-2, win pools 1st); LOST on dead legs; WON only with scraped tote dividend; else PENDING.
* ATR-window guard: exotic auto-settle only for age ≤ 1 day (older can never be verified).
* Dedupe-at-settle (keep earliest, cancel rest with refund) + EXPIRED status for over-age PENDINGs (no money moves) + `cancel_pending_bet` + `POST /api/betting/void` (void|cancel, keyed by existing middleware).
* Meeting gate: drop scan tracks Betfair proves aren't running today; per-track exotic building; snapshot horse-presence validation; Thursday Vaal card re-stamped vaal/2026-09-17 and kept.

## Capabilities

### New Capabilities
- `racecard-integrity`: future-meeting gate and exotic phantom-meeting guard.

### Modified Capabilities
- `settlement-accounting`: exotic leg settlement, ATR-window guard, dedupe, EXPIRED sweep, cancel/void admin.

## Impact

* `core_agent/skills/result_tracker.py`, `core_agent/skills/bankroll_manager/governor.py`, `core_agent/routes/betting.py`, `core_agent/core/strike_tips.py`
* Tests: `test_exotic_settlement.py` (16), `test_meeting_gate.py` (8), governor cancel/expire tests
* Live remediation: phantom JP1 cancelled/refunded; Vaal card re-stamped; 12 early wrong-day LOSTs disclosed, left settled per user steer (void endpoint reverses on request).
