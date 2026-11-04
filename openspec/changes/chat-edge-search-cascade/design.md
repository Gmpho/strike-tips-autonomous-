# Design: Chat Edge Search Cascade

## Context

- `chat.ts` (Pages Function) holds both handlers: `handleGeminiChat` and
  `handleGroqChat`. Today only `gemini-3.5-flash` receives
  `tools: [{ googleSearch: {} }]`; `handleGroqChat` is not even passed the
  `searchGrounding` flag.
- The edge worker exposes `web_search_racing` over `/mcp` (stateless
  JSON-RPC; auth `x-api-key` === worker `BACKEND_API_KEY`, whose value is in
  the local `.env` as `STRIKE_TIPS_API_KEY` — verified live 2026-09-28:
  `provider: "tavily"`, 5 results).
- The edge cascade meters monthly spend in KV and skips exhausted providers;
  it has no keyed free floor beyond Brave (DDGS lives in the backend path).
- Browser-local WebLLM models never reach `chat.ts`; they fetch
  `/api/agent/context` and run inference in-page, so they need a separate
  same-origin bridge to the cascade.

## Goals

- One search path for every model, served by the metered free-tier cascade.
- No `googleSearch` tool, no paid fallback introduced by this change.
- Model-agnostic, mobile-visible Search control with honest attribution.

## Decisions

- Inject results as a system-context block (title / url / snippet) instead of
  provider-specific tool calls — the same shape works for Gemini, Groq, and
  WebLLM prompts.
- `functions/lib/edge-search.ts` holds the single cascade client; both
  `chat.ts` and `search.ts` import it (no duplicated fetch logic).
- Keep the wire flag name `searchGrounding` (UI contract unchanged);
  semantics documented as "edge web search".
- Cascade failure is non-fatal: chat still answers, sources stay empty, and
  the context block explicitly says live search was unavailable.
- Redact nothing → send nothing: the edge key never leaves the server; the
  browser calls `/api/search` keyless.

## Risks

- Budget pressure: default-on search spends Tavily (~1000/mo) then Exa
  (~1400/mo) per chat turn. If chat volume grows, add an edge-side daily cap
  (mirrors the backend 40/day) — tracked as a follow-up, not shipped here.
- Missing Pages secret silently degrades to "search unavailable"; the
  explicit context note is the detection mechanism (plus `provider: "none"`).
- Extra ~0.5–1.5s latency on search turns, bounded by an 8s abort.
- Query = last user message truncated to 200 chars; long pastes may search
  poorly. Revisit with a query builder if it bites.
