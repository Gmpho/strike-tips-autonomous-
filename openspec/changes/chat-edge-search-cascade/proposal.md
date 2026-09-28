# Proposal: Chat Edge Search Cascade

## Why

The chat Search button is wired to Gemini's `googleSearch` grounding tool and
only for `gemini-3.5-flash`; Groq never even receives the flag and
browser-local (WebGPU) models get nothing. The free-tier edge cascade
(Tavily → Exa → Brave) built in `free-tier-search-cascade` is therefore never
reached from chat — verified 2026-09-28 in `strike-tips-hud/functions/api/chat.ts`
(`config.tools = [{ googleSearch: {} }]` at the gemini-3.5-flash branch, no
search parameter on `handleGroqChat`), with zero chat-path references to the
edge `webSearchCascade`.

## What changes

- `strike-tips-hud/functions/api/chat.ts`: every chat web-search request goes
  through the edge MCP tool `web_search_racing` (Tavily → Exa), results are
  injected as a system-context block for **all** models; the Gemini
  `googleSearch` grounding tool is removed.
- New `strike-tips-hud/functions/lib/edge-search.ts`: shared cascade client
  (JSON-RPC over `/mcp`, `x-api-key`, 8s abort, never throws).
- New `strike-tips-hud/functions/api/search.ts`: keyless, rate-limited
  same-origin JSON proxy so browser-local WebLLM models can ground too.
- `strike-tips-hud/src/components/AIChat.tsx`: the Search control renders for
  every model choice (not just Gemini-3.5/auto) and keeps its "Search" label
  on mobile; source chips are attributed to the cascade, not Google.

## Impact

- Additive on Groq/WebGPU: search works where it silently did nothing.
- Removes Google grounding from the chat path; chat search now spends the
  metered edge budgets (KV monthly meters, exhausted providers skipped).
- Protected path touched: `strike-tips-hud/functions/` (explicit user
  approval given 2026-09-28). Requires a Pages secret
  (`MCP_API_KEY`, falling back to `STRIKE_TIPS_API_KEY`/`BACKEND_API_KEY`)
  and a Pages redeploy — deploy is the user's call.
- Honest degradation: cascade dry / key missing → empty sources, the model is
  told search was unavailable; no fabricated URLs.
