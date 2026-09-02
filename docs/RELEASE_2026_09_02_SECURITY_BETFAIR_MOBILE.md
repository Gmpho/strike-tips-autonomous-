# Release 2026-09-02 — Security Hardening, Betfair Enrichment (All Regions) & Mobile HUD Polish

## Overview
Three-track release: **(A) production security** (Cloudflare + Vercel), **(B) Betfair form-data expansion** to 12 fields across all regions, **(C) mobile/tablet responsive & performance** polish for the 12-column RaceCard. All changes verified with `PYTHONPATH=. pytest` (53 tests), `vercel deploy --prod`, `modal deploy`, `wrangler deploy`, and live `curl` probes.

---

## A. Security Hardening — Cloudflare Worker & Vercel Middleware

### Cloudflare Worker `striketips-mcp` (`cloudflare_mcp_edge/src/index.ts:20`)
- **Auth bypass fixed:** `isAuthorized` changed from `!env.BACKEND_API_KEY || header===env.BACKEND_API_KEY` to `!!env.BACKEND_API_KEY && header===env.BACKEND_API_KEY` — fail-closed when secret missing, was fail-open (`isAuthorized:20`).
- **CORS locked:** `*` replaced with allowlist `https://strike-tips-hud.vercel.app` (+ `http://localhost:3000/5173` for dev) via `ALLOWED_ORIGINS:24` + `corsHeaders(request):31` + `Vary: Origin`. Preflight `OPTIONS 204` added (`src/index.ts:556`).
- **Headers normalized:** `json()` now takes optional `Request` to set per-origin `Access-Control-*` (`json:48`), post-handlers wrap with `corsHeaders` (`src/index.ts:565`).
- **Secret rotation:** `BACKEND_API_KEY` rotated to `7a70174b1f0d6bfa84009329b9800d5013c768fc52d2b1be77084c465201a125` (256-bit) via `wrangler secret put BACKEND_API_KEY` — verified `curl -H "x-api-key: <old>"` now `401`, `curl POST /api/ingest-odds` without key `401` with key passes.

### Vercel Middleware (`strike-tips-hud/middleware.ts:14`)
- **Rate limiting:** fixed-window `RATE_LIMIT_MAX=100 req/min` per IP (`rateStore:16`, `isRateLimited:19`) — returns `429 Retry-After:60`.
- **Kill-switch protection:** `SENSITIVE_PATHS=["/api/agent/kill","/api/agent/reset"]` (`middleware.ts:29`) now requires `x-api-key`/`X-API-KEY`/`Authorization: Bearer` matching `STRIKE_TIPS_API_KEY` (`isAuthorizedRequest:32`) — verified `curl POST /api/agent/kill` without key `401` (was `EMERGENCY STOP ACTIVATED`), with new key passes for `GET /api/betting/account-summary`.
- **IP extraction:** `x-forwarded-for` → `x-real-ip` fallback (`middleware.ts:54`).

### Secrets
- `STRIKE_TIPS_API_KEY` rotated in `.env:5`, `modal secret create strike-tips-api-key --force` (`core_agent/core/security.py:5` reads `STRIKE_TIPS_API_KEY`), `vercel env add STRIKE_TIPS_API_KEY production --force`. Modal `security.py:35` already enforces `X-API-KEY` except `SAFE_PATHS`.

**Verification**
```bash
curl -X POST https://strike-tips-hud.vercel.app/api/agent/kill  # 401 {"error":"Unauthorized"}
curl -H "x-api-key: 7a70..." https://gmpho--strike-tips-racing-serve-api.modal.run/api/betting/account-summary  # 200 R3799
curl -I -H "Origin: https://evil.com" https://striketips-mcp.gmphorg379.workers.dev/api/health  # allow-origin: https://strike-tips-hud.vercel.app (not *)
```

---

## B. Betfair Form-Data Enrichment — All Regions, 12 Fields

### Scope
Was SA-only (`_COUNTRY_FILTER={"ZA"}`), 2 fields (`gear`, `daysSinceRun`). Now **all regions** (`_COUNTRY_FILTER=None`) and **12 fields** per runner, displayed on HUD.

### Parser (`core_agent/skills/parsers/betfair_sa.py:47`)
- `_COUNTRY_FILTER=None` (`betfair_sa.py:47`) — `get_form_format` now collects `marketId` **or** `id` (`betfair_sa.py:169` `market.get("marketId") or market.get("id")`) from `TODAY`+`TOMORROW` across RSA/AUS/FRA/NZL/USA/IRE/GB — verified `TOMORROW` now 169 events (was 0 due to `marketId` miss + lowercase `wearing`).
- Case-insensitive lookup (`meta_low:236` + `_get()`) — handles Betfair uppercase `WEARING`, `DAYS_SINCE_LAST_RUN`, `OFFICIAL_RATING`, `OWNER_NAME`, `TRAINER_NAME`, `WEIGHT_VALUE`, `FORM`, `AGE`, `JOCKEY_CLAIM`, `runnerName` vs `runnername`.
- Helpers: `_clean_str:90`, `_parse_int_field:98` (now `int(float(s))` handles `"3.0"`).
- Pedigree construction from `SIRE_NAME x DAM_NAME (DAMSIRE_NAME)` when `pedigree` absent (`betfair_sa.py:255`).
- Weight as `"128.0 pounds"` (`WEIGHT_VALUE` + `WEIGHT_UNITS`), trainer via `TRAINER_NAME`, owner via `OWNER_NAME`.
- `market_info` map (`betfair_sa.py:146`) stores `course`/`timeLabel`/`raceName` from `/all` so `_parse_market` no longer relies on `marketStartTime` → SAST conversion (which was +2h off: `11:07` became `13:07`).

### Data Model
- `tab4racing.py:31` `ScrapedRunner` added `gear`, `days_since_run`, `runner_comments`, `jockey_claim`, `official_rating`, `pedigree`, `owner`, `verdict` (all `Optional`).
- `analyzer.py:14` `Runner` added same 8 fields + `age`/`sex` handling.
- `racing_service.py:115` `_convert_race_data` now passes through `age`, `sex`, `gear`, `days_since_run`, `runner_comments`, `jockey_claim`, `official_rating`, `pedigree`, `owner`, `verdict`.

### Merge (`core_agent/core/adaptive_odds_monitor.py:198`)
- `_merge_bf_into` now loops 12 keys (`gear`, `daysSinceRun`, `runner_comments`, `jockey_claim`, `official_rating`, `pedigree`, `owner`, `verdict`, `trainer`, `age`, `weight`, `form`) — additive only, `key not in bw_runner`, one-to-one via `matched_bf_indices` + `difflib 0.6` (`adaptive_odds_monitor.py:284`).

### HUD (`strike-tips-hud/src/types/index.ts:21`, `RaceCard.tsx:81`)
- Types: `Runner` now `gear?`, `daysSinceRun?`, `runner_comments?`, `jockey_claim?`, `official_rating?`, `pedigree?`, `owner?`, `verdict?`, `age?: string|number`.
- Table: `Gear` badges (`split(' · ')` cyan), `Days` sortable, expanded row grid shows 8 fields (`Gear`/`Days`/`Comments`/`Verdict`/`Rating`/`Claim`/`Pedigree`/`Owner`) (`RaceCard.tsx:525`).
- Cards (mobile): collapsed shows `Gear`, `Days`, `Owner`/`Pedigree` preview (`RaceCard.tsx:362`), expanded shows same 8-field grid (`RaceCard.tsx:395`), `hasEnriched` now includes `gear`/`daysSinceRun` so gear-only runners are expandable.

**Verification**
```bash
PYTHONPATH=. pytest test_betfair_sa test_merge_betfair test_betfair_enriched -q  # 53 passed
python -c "from core_agent.skills.parsers.betfair_sa import BetfairSA; ..."  # TOMORROW 169 events, Durbanville R1 11:07 12 runners with pedigree/owner/rating
curl https://gmpho--strike-tips-racing-serve-api.modal.run/api/racing/odds | jq '.events[].runners[] | {name, gear, pedigree}'
```

**Note:** `runner_comments`/`verdict` are absent in Betfair SA payload for Durbanville (only `FORM`/`pedigree` populated) — HUD renders them only when present, without placeholder noise.

---

## C. Mobile, Tablet & Performance Polish

### Viewport & Scroll (`strike-tips-hud/index.html`, `style.css`)
- `viewport-fit=cover`, `overflow-x:hidden; max-width:100vw; overscroll-behavior-x:none; -webkit-overflow-scrolling:touch` — stops 12-col table from panning body.

### RaceCard (`RaceCard.tsx:81`)
- Sticky horse col: `sticky-col-cell bg-theme-panel z-10` (`#0c0817` dark / `#ffffff` light, high z-index) — numbers no longer bleed through.
- Removed `tracking-tighter` on titles/buttons.
- View toggle: `viewMode: table|cards` (`RaceCard.tsx:86` + `LayoutList`/`TableIcon`), `sm:hidden` cards vs `min-w-[720px]` table with `touch-scroll-x`.
- Cards collapsed: form/edge/days/gear/owner/pedigree; expanded: 8-field grid.

### Content & LCP (`style.css`, `App.tsx`)
- `content-visibility:auto; contain-intrinsic-size:0 160px` on cards — skips off-screen paint, slashes LCP.
- Removed stagger delays, removed `mode="wait"` on tab transitions → instant (0ms) switch.

### Navigation
- `BottomNav.tsx` glass dock (<768px) 5 items (Races, AI Chat, Exotics, Bankroll, More) + `pb-24 md:pb-8` + `env(safe-area-inset-bottom)` so dock never overlaps.
- `Header.tsx` 320-480px scaling without wraps.

**Verification:** `vercel deploy --prod` (`bhtrxej6j` 47s, `i05ikjx79` 49s) — `tsc --noEmit --skipLibCheck` clean after `MarketMoversView.tsx:276` `String(age)` fix; `vite build` chunk `YTZ8twO5` 74.9kB.

---

## Deployments (straight commands, no watch)
```bash
modal deploy core_agent/core/modal_app.py  # 390s, serve_api https://gmpho--strike-tips-racing-serve-api.modal.run
modal deploy core_agent/core/ollama_cloud.py
vercel deploy --prod --yes --force --cwd strike-tips-hud  # aliased https://strike-tips-hud.vercel.app
npx wrangler deploy  # striketips-mcp 66cf38a3, 159 KiB
printf "7a70..." | wrangler secret put BACKEND_API_KEY
printf "7a70..." | vercel env add STRIKE_TIPS_API_KEY production --force
```

## OpenSpec
`openspec/specs/betfair-form-data/spec.md` updated: Purpose 12 fields + `_COUNTRY_FILTER=None`, Requirement extraction 12 keys, Merge 12 keys additive one-to-one, HUD 8-field expanded row + all-regions scenario, `openspec status --json` clean.

## Risk & Rollback
- More Betfair API calls (all regions, 169 vs 8 for TOMORROW) — bounded `Semaphore(8)`, 6h `betfair_form_last_good.json` fallback.
- Snapshot size + HUD expanded rows — optional fields omitted when absent, no new fetch.
- Rollback: `git revert bhtrxej6j` or `wrangler secret put BACKEND_API_KEY` old value + `vercel env add` old key.

## Files Touched
`cloudflare_mcp_edge/src/index.ts:20`, `strike-tips-hud/middleware.ts:14`, `betfair_sa.py:47`, `tab4racing.py:31`, `analyzer.py:14`, `racing_service.py:115`, `adaptive_odds_monitor.py:198`, `types/index.ts:21`, `RaceCard.tsx:81`, `MarketMoversView.tsx:276`, `style.css`, `index.html`, `BottomNav.tsx`, `wrangler.jsonc`
