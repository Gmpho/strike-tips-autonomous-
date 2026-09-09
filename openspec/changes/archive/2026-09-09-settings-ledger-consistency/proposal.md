## Why

Three consistency defects made settings feel broken and money confusing:
(1) saved bankroll-protocol values (Starting Balance, Max Stake %, Daily
Stop %, Min Edge) always reloaded as hardcoded defaults — `GET /config`
never overlaid the saved keys, so every save appeared to vanish on reload;
(2) Starting Balance only ever touched the real ledger (and only pre-P&L),
so paper-mode saves silently did nothing; (3) the HUD showed one balance
under two names ("Capital" vs "Current Bankroll") with no ledger identity,
while the 5-second poller rebuilt the bankroll object WITHOUT
paperMode/paperBalance/realBalance — permanently flipping the UI to LIVE
even in paper mode; (4) the Exotics Settle Ledger filtered a `betHistory`
store that only hydrates on bankroll/analytics views, so it read permanently
empty on the exotics view.

## What Changes

- `GET /config` overlays saved flat keys onto the bankroll block
  (total_bankroll, max_bet_percent, daily_loss_limit, min_edge_threshold).
- `POST /config` startingBalance is paper-aware: in paper mode it resets the
  paper bank + refill target, but only when the value actually changed (so an
  unrelated toggle-save never wipes the bank as a side effect).
- `BankrollState` gains `realBalance`; the data-bridge preserves
  paperMode/paperBalance/realBalance on every poll.
- Header Capital gains a PAPER/LIVE badge with explanatory tooltip;
  BankrollView shows the active bank plus the untouched other ledger.
- `betHistory` hydrates on the exotics view so the Settle Ledger populates.
- Settings load retries with backoff (cold-container safe) instead of
  sticking at defaults after one failed fetch.

## Capabilities

### New Capabilities
- `settings-ledger-consistency`: settings round-trip integrity, dual-ledger
  identity in the HUD, and ledger hydration coverage.

### Modified Capabilities
(none — no prior spec covered settings or HUD state.)

## Impact

- `core_agent/routes/config.py` (overlay + paper-aware reset + change guard)
- `strike-tips-hud/src/types/index.ts` (`realBalance`), `Header.tsx`
  (badge), `BankrollView.tsx` (ledger split), `engine/data-bridge.ts`
  (field preservation + exotics hydration), `SettingsView.tsx` (retry load)
- Verified live: full save→reload round-trip on prod (3800s persist,
  min-edge 5→6→5), PAPER badge correct, ledger lists all 10 exotic tickets.
- Documented truth table: Max Stake % / Daily Stop % / Min Edge are
  display-only (governor enforces hardcoded 5/20/5); wiring them into the
  governor is explicit follow-up, not this change.
