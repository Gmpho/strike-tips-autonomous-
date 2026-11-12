# Proposal: Settle league picks by off-time, not by the feed's race number

Race numbers are **not portable between feeds**. The market snapshot takes
`raceNumber` from Betway, and Betway numbers US meetings differently from
ATR: ATR's card for Horseshoe Indianapolis on 12-Nov lists 11 races with R1
at 18:30, while the snapshot labels that same race "R4" (the runner counts
match ATR exactly: 10, 7, 14, 8, 13 …).

A league pick records the **feed's** race number, and settlement resolves the
race by `(date, course, race_number)` against ATR — so the pick is settled
against the *wrong race*.

Proven on 2026-11-11 (Horseshoe Indianapolis):

| Pick | ATR truth | Recorded | Outcome |
|---|---|---|---|
| Apotheon | **R1, won** (off 18:30) | R3 | settled a **LOSS** (0 points) |
| Four Star General | **R2, 2nd** (off 19:05) | R4 | pending; would have been lost against the R4 card |

Audit: 122 league picks with ATR off-times, exactly **2** mismatched (both
Horseshoe, both +2). Bankroll: 79 bets checkable against ATR — **none**
settled against the wrong race, so no money moved wrongly.

This change keys a pick's race by the one identifier every feed agrees on —
the **off time** — and repairs picks whose stored number disagrees with the
race ATR proves for that instant. It never guesses: a pick whose horse is on
neither card stays PENDING.

Out of scope: the bankroll ledger (its bets and their results come from the
same feed, so they are self-consistent), and the odds feed's own numbering
(another feed's numbering is its own business).
