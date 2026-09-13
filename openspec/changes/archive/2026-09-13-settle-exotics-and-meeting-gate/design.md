## Context

Exotics were skipped by design ("needs dividends") and queued PENDING forever. The first leg-settler worked but scored Sep-10/11 tickets against Sep-12 ATR pages and recorded same-day dupes 4× via overlapping runs. Separately, TAB serves next-meeting cards early; Thursday Vaal entered Sunday's scan, the AI picked its horses, and first-dict-key labelling stamped the play "turffontein" — taking a real R9.60 ticket.

## Goals / Non-Goals

**Goals:** exact-money exotic settlement (LOST needs no dividend), wrong-day settles impossible by construction, duplicates impossible by construction, future cards impossible by construction.

**Non-Goals:** dividend-history backfill; changing single-bet ATR window (same theoretical issue, working, out of scope).

## Decisions

* Leg pass = banker-OR-saver meets requirement (tickets are banker+saver permutations, not single lines).
* WON never settles on the placement estimate (estimates like 2700x are pool-size artefacts, not dividends).
* Age ≤ 1 for exotic auto-settle mirrors ATR's serving window exactly.
* Dedupe key (track, date, horse) matches the recorder's own idempotency key.
* EXPIRED moves no money; VOID/cancel refunds; void reverses settles. Three distinct terminals, tested separately.
* Meeting gate fails open on unknown courses (a Betfair gap must never wipe a real meeting); snapshot horse-presence is the backstop, not the gate.
* The 12 early wrong-day LOSTs were left settled per explicit user steer; the void endpoint reverses them on request.
