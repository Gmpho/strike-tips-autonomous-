# Tasks: Supabase Ledger + Auth

## 1. Spec + schema

- [x] 1.1 Scaffold `openspec/changes/supabase-ledger-auth/` (proposal/design/spec/tasks) and verify `openspec validate supabase-ledger-auth` passes
- [x] 1.2 Schema applied live (3 migrations: create_ledger_tables, enable_ledger_rls, add_ledger_indexes); advisors run — 0 issues on our objects
- [x] 1.3 Migration history captured via MCP (versions 20261001193638/53/51 visible in list)

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
