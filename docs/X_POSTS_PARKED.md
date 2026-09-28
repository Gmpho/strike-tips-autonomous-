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
   per-post opt-in.
3. Per-user daily post cap + 402 pause-and-alarm in the adapter
   (spec in `openspec/changes/composio-creation-tools/` already requires
   this shape for `publish_tip_post`, currently dry-run only).

## What ships instead (free)

- X intent links (URL, not API): user taps, X composer opens pre-filled
  in their session, they post. $0 for everyone, no billing relationship.
- Auto-post via OAuth stays a documented non-goal until the trigger above.
