# Supabase Ledger + Auth (Oct-2026)

Postgres on Supabase Free (`strike-tips`, `jqemrzfzsdgfclzgycyx`, eu-west-1) is the
future source of truth for money + identity. JSON files on the Modal volume remain
live until the dual-write cutover. Nothing here deletes anything.

## Project & keys

| Item | Value / location |
|------|------------------|
| Project | `strike-tips` (Free, eu-west-1, Postgres 17) |
| URL | `https://jqemrzfzsdgfclzgycyx.supabase.co` |
| Publishable key | `sb_publishable_…` (HUD `VITE_SUPABASE_PUBLISHABLE_KEY`, Pages build env) |
| Service-role key | Modal secret `supabase-strike-tips` (NEVER frontend/git) |
| Local dev | root `.env` (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) |

Mounted on Modal via `modal.Secret.from_name("supabase-strike-tips")` in
`core_agent/core/modal_app.py`.

## Schema (`supabase/schemas/`, declarative)

Tables: `profiles`, `ledger_epochs`, `bankroll_snapshots`, `bets`, `settlements`,
`exotics`, `telegram_links`. Conventions: `numeric` money, identity PKs, FK cascade
to profiles, `unique(user_id, ref, is_paper)` for idempotent imports, `is_paper`
flag keeps the R13k paper bank as a parallel ledger.

RLS on every table, owner-only (`(select auth.uid())` form). Grants: `service_role`
ALL, `authenticated` CRUD (row-governed), `anon` nothing. Auto-expose OFF by design.

Applied via MCP `apply_migration` (history in `list_migrations`); regenerate local
migration files with `supabase db pull` when the CLI is available.

## Auth configuration (dashboard, must match)

- Google provider enabled (OAuth client, callback
  `https://jqemrzfzsdgfclzgycyx.supabase.co/auth/v1/callback`).
- **URL Configuration**: Site URL `https://strike-tips-hud.pages.dev`; Redirect URLs
  `https://strike-tips-hud.pages.dev/**`, `https://*.strike-tips-hud.pages.dev/**`,
  `http://localhost:3000/**`. (Wrong Site URL = prod logins bounce to localhost.)
- Leaked-password protection: enable (hygiene; Google-only auth).

## Backend (`core_agent/db/`, new package — governor untouched)

- `client.py`: `get_service_client()` (Modal only) vs `get_user_client(jwt)` (RLS).
  Transport is PostgREST (no prepared statements → Supavisor-safe).
- `repository.py`: bets/snapshots/epochs/settlements + passcode links (sha256-hashed
  `ST-` codes, single-use, 15-min expiry).
- `import_ledger.py`: dry-run default; reconciliation gate (row census + settled P&L
  for real AND paper must match source) or abort. Paper migrates too.

## Telegram passcode linking (CryptoPulse-style)

Endpoints (`core_agent/routes/telegram_link.py`, JWT-verified in-handler, SAFE_PATHS):
`POST /api/telegram/link-code`, `GET /api/telegram/link-status`,
`POST /api/telegram/unlink`, `POST /api/telegram/test`, `GET /api/telegram/bot-name`.
Bot: `/start ST-XXXXX` redeems (webhook + polling), binds chat ↔ `auth.uid()`.
HUD: `TelegramLinkCard` in Settings (NOT LINKED/CONNECTED states, Turnstile-gated).

## HUD auth gate

Logged-out → `LandingPage`. Logged-in → app. Support + legal views stay public
with a guest banner. Gate activates only when `VITE_SUPABASE_*` present at build.
Sidebar identity: avatar + first name; raw emails never rendered (`maskEmail`).

## Costs (Free tier posture)

- Ledger volume is KBs/day — 500MB DB headroom is effectively infinite.
- Egress diet: list reads project columns, never `SELECT *`.
- Modal: odds monitor skips 23:00–05:00 SAST + dark-day fail-open skip
  (`core_agent/core/racing_hours.py`).
- Log-query allowance is burned by Studio/MCP reads — query narrow windows only.
