# Email Alerts via Resend + Composio — Plan & Status (Sep-2026)

> Privacy: no subscriber addresses, API keys, or sheet IDs in this file.
> Those live in the operator's sheet / env only.

## Status: sandbox-proven, parked pending a sending domain

End-to-end loop verified with Resend sandbox + Composio Sheets:
sheet roster → Resend send → Sheet audit log. Live test mail delivered
and opened. Paused here until a project-owned domain is verified
(`pages.dev` subdomains cannot be verified — Cloudflare owns that DNS).

## What works today

- Resend CLI authed (OAuth profile), `doctor` green, zero domains.
- Dry-run + simulated send (`delivered@resend.dev`) + one live sandbox
  send to the account address (opened, confirmed).
- Composio logged in (`gmphorg379_workspace`); `googlesheets` toolkit
  linked; sheet with `Subscribers(chat_id,email,alerts_opt_in,created)`
  and `AlertLog(ts,type,recipient,idempotency_key,status)` tabs created,
  headers written, seed row + delivery logged via API.
- Discovered slugs: `GOOGLESHEETS_GET_SHEET_NAMES`,
  `GOOGLESHEETS_VALUES_GET`, `GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW`,
  `GOOGLESHEETS_BATCH_GET`, `GOOGLESHEETS_ADD_SHEET`,
  `GOOGLESHEETS_VALUES_UPDATE` (needs `value_input_option: "RAW"`).

## Conventions (do not drift)

- Single sends only (`POST /emails`); batch is atomic and forbids
  attachments/scheduling.
- Idempotency keys: `alert-email/<alert-id>` (24h window) — monitor
  retries must never double-send.
- Sandbox delivers ONLY to the Resend account address; anything else
  403s. `delivered@resend.dev` for simulations, never fake inboxes.
- Sheets mirror; backend store stays source of truth for prefs/ledger.

## Go-live checklist

1. Buy/own a domain (~R200/yr local) — optional: also front the HUD.
2. Resend dashboard → Domains → add records (SPF/DKIM) at registrar → Verify.
3. `RESEND_API_KEY` → repo `.env` (gitignored) + Modal secret
   `strike-tips-secrets` + Pages env. Never in code.
4. Backend sender module (Python SDK ≥2.34) behind the gateway email
   channel; wire critical alerts first, then settles, then digests/reports.
5. Address capture: Telegram `/email` command + HUD Settings field,
   synced to the same prefs store (sheet mirrors).
6. Warm-up: day-1 sandbox-style volumes only (~150 mails), ramp up.
7. Quotas to watch: Resend free 3k/mo + 100/day; Gmail API fallback
   500/day (free) — Resend stays primary.
