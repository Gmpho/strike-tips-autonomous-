# X Auto-Posting — PARKED (tip-jar gated)

> Decision Sep-2026: ship Telegram + Email + Sheets + X-intent links.
> Auto-posting to X stays out until tip-jar revenue funds per-post spend.
> No code for auto-post exists; nothing to remove.

## Why parked

- X pay-per-use (verified Sep-2026): **$0.015 plain post, $0.20 with URL**,
  prepaid credits, 402 when empty. No free tier for new developers.
- X bills the app owner (us), not the subscriber. Link-heavy tipping
  content would be $0.20/post — the exact shape that burns a pool.
- Composio toolkit is `twitter` (79 tools), not `x`; auth is dashboard
  OAuth against our own X developer app (pay-per-use project).

## Revisit trigger (all must hold)

1. Tip jar covers a monthly credit pool with a console spending cap set.
2. Posts are link-free by default ($0.015); URL posts need explicit
   per-post opt-in. (Code is currently stricter: `publish_tip_post`
   strips URLs outright — no opt-in path exists yet.)
3. Per-user daily post cap + 402 pause-and-alarm in the adapter
   (spec in `openspec/changes/composio-creation-tools/` already requires
   this shape for `publish_tip_post`; today only the 5/day cap and the
   `dry_run=True` default exist — 402 pause-and-alarm is NOT implemented).

## What ships instead (free)

- X intent links (URL, not API): user taps, X composer opens pre-filled
  in their session, they post. $0 for everyone, no billing relationship.
  **Status: PLANNED — not built** (verified 2026-09-28: no intent-link
  code in the HUD or backend; `intent/tweet` greps return nothing).
- Auto-post via OAuth stays a documented non-goal until the trigger above.

## See also

- Governing spec: `openspec/changes/composio-creation-tools/` — Requirement
  "Spend-bounded posting" covers `publish_tip_post` (dry-run today).
- Pricing re-verified 2026-09-28 against X's own pay-per-use docs:
  `Post: Create $0.015` / `Post: Create (with URL) $0.200`, prepaid
  credits, spend limits block requests — the figures above still hold.
