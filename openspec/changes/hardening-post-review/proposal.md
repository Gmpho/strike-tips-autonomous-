# Proposal: Post-Review Hardening (5 fixes)

External review (verified line-by-line against code, Oct-2026) found five
real defects ranked by money-risk. This change fixes all five, in order,
each with regression tests. No behavior change beyond the fixes.

1. Corrupt `bet_history.json` + any rejected bet = history rewritten as []
   (governor `_load_state`/`_save_state` interaction).
2. `/v1/*` Pages proxy performs no inbound key check (comment claims it).
3. Winner-extraction pattern 5 unanchored + confidence 1.0 on fuzzy scrape.
4. DSI is an unsmoothed frequency ratio over RNG-fed dreams, labeled Bayesian.
5. Ledger↔Postgres reconciliation runs at import only; settlements drift.
