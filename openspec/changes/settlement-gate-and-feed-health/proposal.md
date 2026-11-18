# Proposal: Settlement Gate Ordering & Feed Health (4 fixes)

Wed 18 Nov 2026, before Kenilworth R1 (13:07 SAST). All four were observed in
the live system that morning — none are speculative. Each fix is one site,
each has a regression test, and no behaviour outside the fix changes.

1. **Exotic settle pass looks up results before it checks the clock.**
   `_settle_exotic_ticket` called `_exotic_leg_races()` (monitor cache +
   Raceform + ATR `/results`) *before* the last-leg off-time gate, so every
   sweep walked result sources for 13–16 tickets whose races had not run and
   then logged `no_results`. `settlement_diagnostics.jsonl` grew 21 KB → 174 KB
   in 24h (983 rows; 695 of them this exact case), and `_exotic_leg_races`
   builds a fresh `AtTheRacesAPI()` per call — one uncached ATR `/results` hit
   per ticket per sweep (~50 sweeps/day). Its the strongest candidate for the
   6h ATR breaker trips that blinded the results tab.

2. **The HUD never reads `stale` / `fetch_ok`.** During the Betway 403 waves
   the card stays on screen looking live while every price is hours old. The
   payload already carries the flags; nothing consumed them.

3. **One ATR breaker trip logged five times.** `_record_failure` warned on
   every failure past the threshold, including half-open probes, so a single
   trip read as `TRIPPED` ×5 with the cooldown unchanged.

4. **QUARTET void/re-record churn.** Two calls in one scan with identical
   selections voided the first ticket and re-added a copy 1 s later, leaving a
   VOID + PENDING pair for the same pool on the board.

Out of scope (deliberately): Betway 403 mitigation, ATR/OTB source changes,
`vercel.json`, and anything touching settlement math or the ledger.
