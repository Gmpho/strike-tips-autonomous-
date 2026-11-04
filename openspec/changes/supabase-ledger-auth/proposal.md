# Proposal: Supabase Ledger + Auth (L7 Migration)

## Why
Money state (bankroll, bets, settlements, exotics) lives in JSON files on
the Modal volume: no transactions across files, no queries, single-box
durability. Telegram auth is a shared PIN + `whitelist.json`. This change
moves the ledger to Postgres on a fresh Supabase Free project and adds
Google Auth with per-user RLS isolation — zero data loss, user-chosen
fresh-start epochs, CryptoPulse-style passcode Telegram linking.

## What changes (all new files; protected paths untouched)
- `supabase/schemas/` — declarative schema (profiles, bankroll_snapshots,
  bets, settlements, exotics, telegram_links) with RLS + indexes.
- `core_agent/db/` — new package: pooled Supabase/Postgres client
  (Supavisor transaction mode) + repository layer. Governor is NOT edited;
  it gains a dual-write call behind a flag in a later change with explicit
  approval.
- `core_agent/db/import_ledger.py` — one-off JSON→Postgres import with
  reconciliation gate. Imports the FULL history (production counts
  ~1490 rows: settled + PENDING opens + VOID/EXPIRED; paper bets excluded
  — paper has its own balance). Gate: row counts per status + SUM(profit)
  over settled (latest verified: balance R3799.56, P&L +R2799.56) or abort.
- HUD Settings: ledger-mode toggle (carry history / start fresh epoch)
  and Telegram Alerts passcode card (follow-up wiring, same change).
- PIN auth retired only after passcode flow is verified live.

## Impact
- No behavior change until dual-write flag flips (separate change).
- New unit tests only; existing suites untouched.
- Blocked on live verification until user supplies project ref + keys.
