# Database security posture — strike-tips (jqemrzfzsdgfclzgycyx)

Audited 2026-11-06 with the Supabase MCP advisors. This is a **decision record**:
it says what is safe, what is noise, and what must not be "cleaned up" later.

## Advisor state at audit time

| Advisor | Result |
|---|---|
| Performance | 12 × `unused_index` (INFO) — **not actionable**, see below |
| Security | 1 × `auth_leaked_password_protection` (WARN) |
| Health | clean (0) |

## Verified posture (beyond what the linters report)

- **RLS enabled on all 13 `public` tables**, each with ≥1 policy.
- **`anon` has no `SELECT` / `INSERT` / `UPDATE` / `DELETE`** on any table — only
  inherited `REFERENCES / TRIGGER / TRUNCATE`, which PostgREST cannot reach.
  A leaked publishable key therefore reads nothing.
- **The HUD bundle carries only the publishable key.** `strike-tips-hud/.env`
  defines `VITE_SUPABASE_URL` + `VITE_SUPABASE_PUBLISHABLE_KEY`; `grep
  service_role dist/assets` returns nothing. The service-role key stays in
  Modal secrets (backend only).
- **All 65 auth users are Google OAuth with no password set**
  (`encrypted_password is null` for every row).

## Decision: the 12 unused indexes stay

`pg_stat_database.stats_reset` = 2026-09-29. Ten of the twelve flagged indexes
sit on tables with **0 live rows** — an index cannot be used against an empty
table, so the notice is a volume artefact, not a missing/damaged index.

The live league and ledger data is the **Modal volume JSONL** (`league_picks.jsonl`,
`bet_history.json`), not the `public.league_*` / `bets` / `settlements` tables.
Those tables are a schema stub for a future mirror (`supabase/schemas/league.sql`).

`telegram_links_chat_idx` is a false positive too: 60 rows, 180 seq scans vs 154
index scans — the planner correctly prefers a sequential scan at that size.

**Do not drop these to "tidy up" the advisor.** Total cost is ~96 KiB. The only
genuinely redundant one is `league_picks_user_race_idx` (`user_id, race_id`),
whose columns are already a strict prefix of the unique constraint
`league_picks_user_id_race_id_rank_in_slip_key`; dropping it is safe but
optional.

## Outstanding (manual, Dashboard only)

Authentication → Attack Protection → **Prevent use of leaked passwords**.

Not available through the Supabase MCP (no auth-config tool exposed) and no
access token is configured in this environment. It is a belt-and-braces toggle:
with zero password users it protects nothing today, but it must be on before
email/password auth is ever enabled.

Verify with: `get_advisors(type="security")` → the warning must disappear.
