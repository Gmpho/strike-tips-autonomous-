# Settlement — Singles, Exotics, Voids & Abandonments

How open tickets become WON / LOST / VOID / EXPIRED. Money rules first,
mechanics second.

## Status meanings

| Status | Meaning | Money |
|---|---|---|
| `PENDING` | Awaiting result | Stake held |
| `WON` | Winner confirmed (+ exotics: with scraped tote dividend) | Profit paid |
| `LOST` | Confirmed beaten | Stake lost |
| `VOID` | Ticket should never have stood (duplicate, phantom, scratched, abandoned) | **Stake refunded, P&L untouched** |
| `EXPIRED` | Too old to ever verify (>3d, ATR serves today/yesterday only) | No money moves |

VOID refunds from whichever ledger took the stake (paper vs real). VOIDs are
excluded from D1 learning mirrors and ROI stats — a refund is not a result.

## Singles

1. **Off-time gate** — a race that hasn't run (+15 min grace) is never settled.
2. **Non-runner void** — Betfair `REMOVED` + Betway `nonRunner` flags flow
   through the snapshot merge (`non_runner: True`, Betfair-only NRs injected
   as `odds: "NR"`). A scratched horse can neither win nor lose: the ticket
   is VOIDed with refund instead of scored.
3. **Winner match** (ATR → DDGS fallback, ≥0.55 fuzzy) → WON (`placed: "1st"`).
   A confirmed different winner → LOST, with `placed` captured from ATR
   (`2nd`/`3rd`/…) for place-pool signal.
4. **Abandoned meetings** — past last off +90 min, ATR serving the day fine
   overall, zero results for the track → VOID all PENDING singles with
   refund + one Telegram note per meeting. Checked at most once per
   (day, track) via `.abandon_checked_*` markers. Singles only.

## Exotics (PA / Bipot / Pick 6 / Jackpot)

- Leg requirements: PA 1st/2nd/3rd, Bipot 1st/2nd, Pick 6 & Jackpot 1st only.
- A combination passes when the banker **or** a saver meets the requirement;
  dead only when a leg's results are confirmed and every candidate is
  outside it. Unknown keeps the ticket PENDING.
- WON only with a scraped tote dividend. Abandoned legs: tickets stay
  PENDING (tote abandoned-leg rules are a follow-up, not yet implemented).
- Build guards: phantom-meeting check (≥half bankers run today), balance
  check (≥half legs anchored ≤6.0 — no all-outsider tickets), NR check
  (no scratched candidate), AI prompt demands favourite/value anchors with
  longshots as savers only.

## Notifications

Settle notifications fire once per (bet, outcome) via `mark_notified`
(volume-persisted, cross-process safe — overlapping monitor runs caused
double-posts before this). Amounts are re-read confirmed post-settle, never
taken from possibly-stale in-memory objects.

## Form-driven ticket budget (punter logic)

`recent_form()` scores the last 20 settled singles (exotics/voids excluded):
HOT (≥40% wins) → 24 AUTO tickets/day, NEUTRAL → 16, COLD (<25% + negative
net) → 10. Stakes stay cautious regardless (Half-Kelly × DSI × odds cap ×
4× delusion gate). Samples under 10 settle to NEUTRAL.
