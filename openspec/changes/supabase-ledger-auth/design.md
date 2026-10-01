# Design: Supabase Ledger + Auth

## Context
- Governor persists via atomic-write JSON + file locks (`governor.py` —
  PROTECTED, do not edit in this change). Reads/writes stay on JSON until
  the dual-write change.
- Modal crons spin containers per invocation → must use the Supavisor
  transaction-mode pooler (port 6543), never direct Postgres (5432).
- Free tier: 500MB DB, 50k MAU, pausable projects. Ledger volume is KBs/day.

## Decisions
- Declarative schema workflow (`supabase/schemas/`, `config.toml`
  `schema_paths`) — generate migrations via `supabase db pull`, never
  hand-write migration filenames.
- `numeric` for all money; `identity` PKs; FK cascade to profiles;
  `unique(user_id, ref)` for idempotent imports.
- RLS everywhere, `(select auth.uid())` form (evaluated once per query).
  Service-role only in Modal secrets for crons; HUD gets publishable key.
- Passcodes: `ST-` + 5 digits, single-use, 15-min expiry, stored hashed
  (sha256) — the code shown once, only the hash persisted.
- "Start fresh" = new ledger epoch row, never DELETE. History stays
  queryable, excluded from live P&L.
- Dual-write + nightly reconcile for one week before flipping reads.

## Risks
- Free-project pause killing the morning scan → mitigated by scan
  fallback to JSON (fail-open on reads, fail-closed on writes) + upgrade
  path to Pro if pauses ever bite.
- Pooler + prepared statements don't mix in transaction mode → use
  simple protocol (no prepared statements) in the repository layer.
