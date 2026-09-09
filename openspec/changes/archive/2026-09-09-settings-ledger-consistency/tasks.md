## 1. Backend settings contract (`core_agent/routes/config.py`)

- [x] 1.1 Overlay saved flat keys onto the `GET /config` bankroll block (total_bankroll, max_bet_percent, daily_loss_limit, min_edge_threshold); verify saved 3800 echoes instead of hardcoded 1000
- [x] 1.2 Make `startingBalance` paper-aware (reset paper bank + refill target); verify
- [x] 1.3 Gate resets on actual value change (`prev_balance` compare) so unrelated saves never wipe a bank; verify toggle-save preserves balances

## 2. HUD ledger identity + hydration

- [x] 2.1 Add `realBalance?` to `BankrollState` (`types/index.ts`); verify tsc passes via prod build
- [x] 2.2 Header PAPER/LIVE badge with ledger tooltip (`Header.tsx`); verify badge reads PAPER in paper mode on prod
- [x] 2.3 BankrollView active-bank + untouched-ledger split line; verify both ledgers visible
- [x] 2.4 Preserve `paperMode`/`paperBalance`/`realBalance` in the data-bridge poll update; verify badge survives repeated polls
- [x] 2.5 Hydrate `betHistory` on the exotics view; verify Settle Ledger lists all 10 recorded tickets on a direct visit
- [x] 2.6 Retry settings load with backoff (4 attempts) + cancelled-guard; verify cold-start self-heal

## 3. Verification

- [x] 3.1 Live API probes: config overlay values, account-summary ledger fields
- [x] 3.2 Live button test on prod: save, min-edge 5→6→reload→6→revert→5→reload→5, backend confirms each step
- [x] 3.3 Modal + Vercel deploys green; settings snapshot shows 3800s + PAPER badge
- [x] 3.4 Host suite green (no backend logic touched beyond config route)
