# Design: Free-Tier Search Cascade

## Context
- Edge worker (always-free): outbound fetch only, KV available, no secrets
  in code. Prior state: Brave-only, unconfigured.
- Backend: `search_racing` was DDGS + httpx scrape; called per bet per
  sweep, per chat message, per agent turn — unbounded.
- Keys live in env (local `.env`, Modal `strike-tips-search`, Pages +
  Worker secrets). Values never in repo/chat.

## Goals
- Every search path prefers free API quality, degrades without billing.
- Loops (monitor, chat repeats) cost zero via cache + caps.
- Model-agnostic: tool layer serves all models.

## Decisions
- Order Tavily → Exa (answers first, semantic second, scrape last).
- Meters beside the code that spends (KV on edge, JSON sidecar backend).
- Exa without paid `contents` (metadata title/url only) — keeps it free.
- X auto-post explicitly out (parked doc), so no spend surface grows here.

## Risks
- Key rotation: stale keys 401 silently → providers skip to DDGS;
  monitor `provider` field in responses to notice.
- Month-boundary races: meters keyed YYYY-MM, reset automatic.
