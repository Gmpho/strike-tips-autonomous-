# Tasks: Supabase Ledger + Auth

## 1. Spec + schema

- [x] 1.1 Scaffold `openspec/changes/supabase-ledger-auth/` (proposal/design/spec/tasks) and verify `openspec validate supabase-ledger-auth` passes
- [ ] 1.2 Write declarative schema `supabase/schemas/*.sql` + `supabase/config.toml` (WRITTEN, awaiting live lint); verify `supabase db lint` (or advisors) passes on live project once keys land
- [ ] 1.3 Generate migration via `supabase db pull` after live apply; verify `supabase migration list` shows it

## 2. Repository layer (new files only)

- [x] 2.1 Create `core_agent/db/` package (client via pooler + repository); verify new unit tests pass with fakes (no live DB needed)
- [x] 2.2 Write `import_ledger.py` with reconciliation gate; verify dry-run against volume JSONs balances to +R2799.56 / R3799.56
- [ ] 2.3 Live import into fresh project; verify row counts + SUM(profit) in SQL

## 3. Auth + linking (needs Google provider enabled)

- [ ] 3.1 HUD Google login button; verify login round-trip on preview deploy
- [ ] 3.2 Passcode endpoints + `/start CODE` webhook; verify link round-trip on own account
- [ ] 3.3 Settings Telegram Alerts card (NOT LINKED/CONNECTED); verify Turnstile gating on all three link endpoints

## 4. Cutover (separate approval — touches governor)

- [ ] 4.1 Dual-write behind flag (governor edit — needs explicit approval)
- [ ] 4.2 Nightly reconcile + Telegram drift alert; verify one clean week
- [ ] 4.3 Flip reads, retire PINs, run advisors; verify full suite green
