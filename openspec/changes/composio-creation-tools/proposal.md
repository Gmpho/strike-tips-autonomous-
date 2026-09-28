# Proposal: Composio Creation Tools (analysis sheets, PnL reports, X posts)

## Why
Subscribers want the agent's work product in *their* accounts: form analysis
in their Drive, weekly PnL in their sheets, tipped slips posted to their X.
Today Composio is operator-only (my CLI session, my sheet). This change adds
per-subscriber connected accounts behind 3 fixed internal tools, keeping the
agent blind to vendors, slugs, and credentials.

## What changes
- New package `core_agent/integrations/` (adapter only — the sole file that
  knows Composio exists).
- 3 internal tools in `core_agent/tools/composio_tools.py`, registered in
  `TOOL_REGISTRY` beside the existing 16: `create_analysis_sheet`,
  `export_pnl_report`, `publish_tip_post`.
- `/connect x|google` + `/post` Telegram command branches (reads + new
  branches only; `modal_app.py` touch needs explicit user approval).
- No changes to settlement, ledger, digest, podcast, or model code.

## Impact
- Additive only. No existing behavior changes; no protected-path edits
  except the Telegram command branches (approval gated).
- Cost: Composio Free cap + X pay-per-use ($0.015 link-free post) with
  per-user daily caps; spend alarms before pools empty.
