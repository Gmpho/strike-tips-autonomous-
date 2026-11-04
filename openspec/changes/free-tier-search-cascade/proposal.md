# Proposal: Free-Tier Search Cascade

## Why
Paid search (Brave) gated all real-time research. Free Tavily + Exa tiers
cover agent + edge chat volumes with budget guards.

## What changes
- Edge `web_search_racing`: Tavily → Exa → Brave cascade + KV meters.
- Backend `search_racing`: Tavily → Exa → DDGS + SA fallback, file
  meters, 40/day cap, 6h query cache.
- Secrets in Modal/Pages/Worker; docs updated; X auto-post documented
  as parked (tip-jar gated).

## Impact
- Additive. No existing behavior changes except provider order
  (DDGS moves from first to free floor).
- Spend: $0 while meters hold; honest degradation after.
