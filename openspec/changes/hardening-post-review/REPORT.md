# Post-Review Hardening Report (Oct-2026)

Response to the external code review ("What Strike Tips actually is").
Every finding was verified line-by-line against the code before fixing.
Reviewer verdict: mostly true. This document records what changed.

## Fix 1 — Corrupt-ledger wipe guard (reviewer finding #3, ranked #1)

**Was true.** `governor.py:240-243` set `self._bets = []` on parse failure,
and `_atomic_transaction` saves unconditionally after yield — one bad byte
plus one rejected bet rewrote history as `[]`.

**Fix** (`governor.py:169-180,211-275`):
- `_load_state` sets `_state_corrupt = True` on any file parse failure
  (error-logged, not warning-whispered) and reseeds from constants.
- `_save_state` refuses entirely while the flag is set.
- Flag reflects the LAST load: repairing the file + any new operation
  clears it, no restart needed.
- Repair path: restore JSON from the backup branch.

**Tests:** `test_ledger_corrupt_guard.py` (4: corrupt blocks save, file
untouched; repair recovers; healthy path saves). `test_governor.py` 20/20.

## Fix 2 — /v1 inbound auth (finding #4)

**Was true.** `functions/v1/[[catchall]].ts` claimed a backend key check in
its header comment and performed none — only a 30/min per-isolate Map.

**Fix:** master `X-API-KEY` OR Turnstile session cookie (via shared
`scopeAllows`, with `/v1/` added to `SESSION_WRITE_PREFIXES`) required for
everything except `/v1/health` + `/v1/models`. HUD needed no change (only
the health pinger touches `/v1/` directly). Rate limit retained underneath.

**Verify:** `npm run build` green (`tsc` + vite); anonymous POST now 401s
without upstream spend (confirm live after Pages deploy).

## Fix 3 — Winner-pattern bound + confidence (finding #2)

**Was true.** Pattern 5 (`name .*? 1st`, no sentence bound) matched across
races/dates over joined DDGS snippets, reporting confidence 1.0.

**Fix** (`result_tracker.py:981-994`): pattern 5 gets the same `[^.?!]`
sentence bound as patterns 1–4 and returns **0.6** instead of 1.0. The
auto-settle threshold is 0.55, so bounded evidence still settles —
calibration now reflects evidence strength.

**Tests:** `test_settlement_chain.py` + `test_exotic_settlement.py` green
(72 passed, 2 skipped) — settle flow behavior preserved.

## Fix 4 — Honest DSI (finding #1, reviewer's top billing)

**Was true.** Raw `neg/total` over RNG-fed dreams (`random.choice` templates,
Bernoulli coin flips), no smoothing, no floor — labeled Bayesian.

**Fix** (`governor.py` DSI block + constants): Beta(2,8) smoothing prior
centers thin evidence near 20% (the no-action zone); `MIN_DSI_DREAMS = 6`
below which the read is labeled heuristic and stakes stay 1.0x. The
dream-generation RNG itself is untouched (separate concern: simulation
inputs, not staking math).

**Tests:** `test_dsi_staking.py` updated to the new contract (4 dreams →
no scaling; 8 dreams at 50% smoothed → 0.75x). Green on host.

## Fix 5 — Continuous reconciliation (finding #7)

**Was true.** `LedgerRepository` money paths had zero production callers;
the gate ran at import only; settlements since drift silently.

**Fix:** `db/compare.py` compares JSON vs Postgres (settled P&L real +
paper, open counts) on demand; docker scheduler runs it 06:30 daily with
Telegram alert on drift only; `reconcile_ledger` Modal function for manual
runs (no cron slot used). Requires `RECONCILE_USER_ID` env or it skips
loudly. **Note:** until dual-write lands, drift is EXPECTED — the alert
proves the wire works, then goes quiet post-cutover.

**Tests:** match + drift cases green (`test_supabase_ledger.py` 30/30).

## Corrections to the review (kept honest)

- `LedgerRepository` is not callerless: link flows use it
  (`telegram_link.py:57`, `modal_app.py:218`, `telegram_gate.py:38`).
  Money paths still don't — the finding stands where it matters.
- Ollama is not fully dead (strict-local mode exists); cloud-outage
  degradation behavior described checks out otherwise.
- `update_learning_job` prints without state change — confirmed, left for
  a follow-up (out of this change's scope).

## Verification status

- Host suites green: governor 20, corrupt-guard 4, settlement 72+2 skip,
  DSI 1, ledger 30, gate/quarantine/link suites green.
- `tsc + vite build` green. Python AST-clean across all touched files
  (compile check caught + fixed a real scheduler.py syntax break pre-push).
- Docker full suite + Modal/Pages deploys: pending approval (this change).
- Protected files touched: `governor.py`, `result_tracker.py`, `modal_app.py`
  — all within the user-approved hardening scope.
