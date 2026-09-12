## Context

Vercel middleware proxied 100% of HUD API traffic (key injection), turning every 5s poll into Fluid CPU + origin transfer. SSE already proved direct-origin works (CORS allows prod origin). Pages Functions bill per invocation (100k/day free), so only keyed traffic may touch them.

## Goals / Non-Goals

**Goals:** unmetered static + reads; secret stays server-side; same UX; Vercel parity (routing, rate-limit, sensitive-path auth).

**Non-Goals:** custom domain (pages.dev first; add to CORS when set), dropping Vercel project (kept paused as fallback).

## Decisions

* Path sets in `backend-origin.ts` mirror Modal `SAFE_PATHS` + worker paths; sync manually on endpoint changes.
* Rewrite only string relative inputs in `apiFetch`; `Request` objects pass through untouched.
* Poll trim 15s/60s acceptable because SSE pushes snapshot changes live.
* `CORP: cross-origin` on backends (readability still gated by CORS); COOP/COEP via `_headers` on `/*` (same-origin proxy responses unaffected).
* One Pages secret `BACKEND_API_KEY`; secret rotation = re-put + no redeploy needed (env-bound at request time, but redeploy to be safe).
