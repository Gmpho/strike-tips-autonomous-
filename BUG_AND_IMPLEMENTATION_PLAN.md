# Strike Tips — Bug & Implementation Plan (Audit Findings)

**Date:** 2026-07-08
**Scope:** Full-stack review of `core_agent` (Python/FastAPI) + `strike-tips-hud` (React/Vite) + data pipeline.
**Mode:** Engineering audit, read-only investigation. No production code changed yet.

---

## 0. Executive Summary

Strike Tips is a well-structured South African horse-racing **value-betting advisory** system (paper-mode by default). The orchestration, bankroll governance, atomic persistence, and HUD are genuinely solid. The audit found **one critical correctness flaw** in the probability-estimation math, several **half-implemented UI/backend features**, and a **stale operations document** that had been reported as a live bug but is already fixed in code.

| Severity | Count | Items |
|----------|-------|-------|
| 🔴 Critical | 1 | Degenerate probability model (value engine inputs unusable under real field sizes) |
| 🟡 Medium | 5 | Stub endpoints, unguarded 500s, unwired bet execution, dead config/routes |
| 🟢 Low/Info | 4 | Display-only indicators, cosmetic copy, minor deps |

> **Important correction:** The `AUTONOMY_PLAN.md` claimed `duckduckgo_search` is missing from `requirements.txt` and that `ResultTracker` has `HAS_DDGS=False` causing silent no-op settlement. **This is stale and false in the current code.** See §1.

---

## 1. CORRECTION — "DDG missing" is already fixed (NOT a live bug)

**Source of the stale claim:** `AUTONOMY_PLAN.md` (P0 #1, P1 #4).

**Verified current state:**
- `requirements.txt:31` → `ddgs==9.11.4` (the correct modern package)
- `core_agent/skills/search_service.py:67` → `from ddgs import DDGS`
- `core_agent/skills/result_tracker.py` → calls `search_racing()` (which uses ddgs); **no `HAS_DDGS` flag exists anywhere** (grep confirms only 1 match for `from ddgs`)
- Environment import check: `ddgs OK 9.11.4`

**Conclusion:** Auto-settlement (`ResultTracker.check_and_settle_open_bets`) is wired and functional against the current code. The `AUTONOMY_PLAN.md` gaps referencing DDG are resolved. **No action required** — but the plan doc should be marked stale so it isn't re-fixed.

**Recommendation:** Add a header note to `AUTONOMY_PLAN.md` stating it was superseded by this audit (2026-07-08).

---

## 2. 🔴 CRITICAL — Probability model is degenerate (the real weakness)

**Files:** `core_agent/skills/race_analysis/form_analyzer.py:60` (`estimate_win_probability`), `core_agent/skills/race_analysis/analyzer.py:119` (`analyze_race` → `edge`), consumed by `core_agent/core/strike_tips.py:416` and `core_agent/services/racing_service.py:122`.

### 2.1 What the code does
`FormAnalyzer.estimate_win_probability` produces a per-horse win probability:
```
base_prob      = (1 / field_size) + (form_rating * 0.4)
adjusted_prob = base_prob * condition_mult
final_prob    = min(adjusted_prob, min(0.75, 2.0 / field_size))   # hard cap
final_prob    = max(final_prob, 0.01)
```
Then `RaceAnalyzer.analyze_race` computes `edge = est_prob - (1 / odds)` per horse, independently.

### 2.2 Proof of the defect (reproduced with the actual code)
Ran `FormAnalyzer` over a realistic 10-horse field (all runners priced @5.0):

| Horse | Form | est_prob | 1/odds | edge% |
|-------|------|----------|--------|-------|
| A | 1-1-2-1-3 | 0.200 | 0.200 | +0.0 |
| B | 2-3-1-4-2 | 0.200 | 0.200 | +0.0 |
| F | 3-2-4-1-2 | 0.200 | 0.200 | +0.0 |
| H | 1-4-2-3-1 | 0.200 | 0.200 | +0.0 |
| E | 9-8-7-9-10 | 0.135 | 0.200 | −6.5 |
| J | 10-9-10-8-9 | 0.123 | 0.200 | −7.7 |
| **SUM** | | **1.859** | 2.00 | — |

**Defects proven:**
1. **Saturation:** the cap `min(0.75, 2/field_size)` = `0.20` for a 10-runner field saturates **every horse with `form_rating ≥ 0.25`** to the identical `0.20`. 8 of 10 horses become indistinguishable.
2. **Not a distribution:** probabilities sum to **1.859**, not ~1.0. They are independent per-horse estimates.
3. **Edge is incoherent:** because `est_prob` is unnormalized, `edge = est_prob − 1/odds` is **not a calibrated probability gap** — it is an arbitrary scalar. The engine cannot detect genuine value; under real odds it reports ~0% on capped horses and negative on poor ones.

**Impact:** The Bankroll Governor, Half-Kelly staking, and Dream Stress Index (DSI) all sit *downstream* of this estimate and multiply a meaningless number by discipline. The only reason "value bets" appear is that the **LLM overlay** (`strike_tips.py:238`) supplies most edges — and that LLM output is itself post-processed by string hacking (`strike_tips.py:255`) and `difflib` fuzzy horse-name matching (`strike_tips.py:312`, cutoff 0.6). There is no calibration and no out-of-sample proof the edge is positive.

### 2.3 Implementation Plan — fix the probability model
**Goal:** make `est_prob` a real, normalized distribution so `edge` is meaningful.

1. Replace the hard cap with a **logistic strength score → softmax** across the field:
   - Compute a raw strength `s_h` per horse from form + conditions (keep recency weights + `condition_mult`).
   - `est_prob_h = exp(s_h / τ) / Σ_k exp(s_k / τ)`, with temperature `τ` tuned so favorite ≈ market favorite.
   - This guarantees `Σ est_prob_h = 1.0`.
2. Keep a sane floor (e.g. `max(est_prob, 0.5 / field_size)`) to avoid zero-stake on longshots.
3. Recompute `edge = est_prob − 1/odds` (note: bookmaker `1/odds` sums to >1 due to margin; that's expected — edge is vs market, not vs a normalized book).
4. **Backtest gate (required before merge):** replay `bet_history.json` + `learning_stats.json`; confirm the normalized model's `edge` correlates with actual win rate (the `/api/betting/learning/roi-by-track` `accuracy = actual_winrate − avg_implied` metric is the natural check). Only ship if accuracy improves vs current.
5. **Guard the LLM overlay:** replace `ast.literal_eval` substring extraction (`strike_tips.py:255`) with strict `response_format=json` (or pydantic parse) and keep `difflib` validation, but log rejected horses instead of silently dropping.

**Risk:** Low–Medium. Change is contained to `form_analyzer.py` + `analyzer.py`; downstream consumers unchanged. Must be backtest-gated (step 4) to avoid regressing live picks.

---

## 3. 🟡 MEDIUM — Stubs, unguarded 500s, unwired features

### 3.1 Healing "pulse" is a no-op stub
- **File:** `core_agent/routes/healing.py:106` (`POST /api/healing/pulse`)
- **Issue:** code comment admits it does not run a scan; it only appends a fake `SYSTEM_PULSE_TRIGGERED` event to `healing_events.json`.
- **Fix:** either call `SelfHealingParser` re-evaluation / re-fetch of selectors, or rename the endpoint to reflect it's telemetry-only. Back it with a real healing pass or return `202 Accepted` with an honest body.

### 3.2 Agent history endpoint is a hardcoded stub
- **File:** `core_agent/routes/agent.py:27` (`GET /api/agent/history`)
- **Issue:** returns `{"history": [], "count": 0}` — never reads memory.
- **Fix:** read from `brain.memory` chat history (the same store `agent/loop.py:76` writes to) and return real turns.

### 3.3 Unguarded 500s
- `core_agent/routes/betting.py:67` `POST /api/betting/place` — no try/except; exception in `place_bet` → 500.
- `core_agent/routes/betting.py:86` `POST /api/betting/settle` — same.
- `core_agent/routes/racing.py:80` `GET /api/scan/{track}` — explicitly raises `HTTPException(500)` on any exception (`:88`).
- `core_agent/routes/agent.py:47` `GET /api/agent/memory/search` — `TOOL_REGISTRY.get("search_past_races")` may be `None` → `TypeError` 500.
- **Fix:** wrap handlers in try/except → `400/422` with error detail; for `memory/search` guard `if tool is None: return 404`.

### 3.4 HUD bet execution is not wired
- **File:** `strike-tips-hud/src/components/RaceCard.tsx:101` ("Execute Position") → `App.tsx:136` only `navigate('chat')`.
- **Issue:** no `POST /api/betting/place` call from the UI. `api-prefixes.ts` defines `history/open/stats/account-summary` but **no `place`/`execute`**. Betting only happens via backend scan/alerts or Telegram.
- **Fix (behind `paper_mode`):** add `place` to `api-prefixes.ts`; on "Execute Position", call `POST /api/betting/place` with the race context. Keep paper-mode default so no real money moves. Surface success/failure in the UI.

### 3.5 Dead config / broken route
- **`/mcp` WebSocket** is proxied in `middleware.ts` + `vite.config.ts` but **no client opens it** → dead config (future intent).
- **`/contact` footer link** (`Footer.tsx:13`) is not in `VALID_VIEWS` (`App.tsx:39`) → renders fallback.
- **Fix:** remove the unused `/mcp` WS proxy or implement a client; add `/contact` to `VALID_VIEWS` or remove the link.

---

## 4. 🟢 LOW / INFO

- **Ollama indicator "OFFLINE" is expected.** `strike-tips-hud/src/sidebar/AgentStatus.tsx` derives status from `GET /v1/health` (`ollama` field in `api_pkg/openai.py:173`); the Ollama container is optional/8GB and usually absent → OFFLINE by design. Not a bug.
- **Agent Pipeline lock toggle is local-only.** `AgentStatus.tsx` `isLocked` updates optimistically; `/api/agent/kill` & `/api/agent/reset` exist but the UI doesn't read server state back. Low risk (cosmetic confidence).
- **Healing "pulse" button** is fire-and-forget (no await/loading/error) — `HealingView.tsx:29`.
- **Unused dep:** `swr` in `package.json` used only by `LegalPage`. Minor bloat.
- **Marketing copy** ("L7 GHOST SYNC ACTIVE") is cosmetic.

---

## 5. Odds-Ingestion Path — verified, with notes

```
Betway API ─┐
racing_odds┼─► AdaptiveOddsMonitor.run() ─► _merge_ro_into() ─► atomic write snapshot
AtTheRaces ┘     (adaptive_odds_monitor.py:236)   (fuzzy, cutoff 0.6)
        │
        ├─ set_snapshot() + Redis publish
        ├─ POST → Cloudflare KV /api/ingest-snapshot (best-effort)
        ├─ ATR snapshots every 3rd cycle → atr_*_snapshot.json
        ├─ intel_cache.update_baseline() (AlertEngine baselines)
        └─ alert_engine.evaluate_odds_update() per event
```

**Notes:**
- Best-odds overlay merges `racing_odds.com` into Betway by `(date, course, time)` with `difflib` 0.6 + ±1 day fallback (`adaptive_odds_monitor.py:59`). Silent mismatches corrupt odds.
- `/api/racing/{market-movers,predictor,results}` are **disk-snapshot readers** — return `[]` if ATR files absent (graceful, but HUD labels them "ATR Intelligence feed," overstating liveness).
- `AlertEngine._maybe_auto_bet` (`alert_engine.py:295`) computes `edge = (1 - implied)*100*0.15` — a **fixed 15% of bookmaker margin**, not a real model edge. Paper-only today, which contains the risk.
- First poll of the day never alerts (baseline seeded on first sighting); stale baselines persist across monitor restart (rehydrated from disk).

---

## 6. Feature Status Matrix (17 surfaces)

| # | Feature | Backend | Status |
|---|---------|---------|--------|
| 1 | Strike Control Dashboard | `/api/monitoring/snapshot` | ✅ Live |
| 2 | AI Agents | `/v1/chat/completions`, `/api/agent/context` | ✅ Live + local WebLLM |
| 3 | Dreaming | `/api/dreaming/logs`, `/api/dreaming/pulse` | ✅ Live (ChromaDB save swallowed by `except: pass`) |
| 4 | Bankroll | `/api/betting/account-summary`, `/history`, `/stats` | ✅ Live (`place`/`settle` can 500) |
| 5 | Analytics | `/api/betting/learning/roi-by-track`, `/bankroll-history` | ✅ Live |
| 6 | Logs | `/api/logs` + synthesized | ✅ Live |
| 7 | Settings | `GET/POST /api/config`, `/test_telegram` | ✅ Live |
| 8 | Racing Intelligence | `/api/racing/intelligence` (PDF) | ✅ Live (group header) |
| 9 | Market Movers | `/api/racing/market-movers` | ✅ Live (disk snapshot) |
| 10 | Predictor | `/api/racing/predictor` | ✅ Live (disk snapshot) |
| 11 | Results | `/api/racing/results` | ✅ Live (disk snapshot) |
| 12 | Admin | `/api/tasks/*` | ✅ Live |
| 13 | Healing Cloud | `/api/healing/activity`, `/selectors`, `/pulse` | ⚠️ 2 live / 1 stub (`/pulse`) |
| 14 | System Vitals | `/api/system/vitals`, `/api/system/health` | ✅ Live |
| 15 | Agent Pipeline / Orchestrator | `/v1/health` + `/api/agent/kill`/`reset` | ⚠️ Weak (lock toggle local-only) |
| 16 | Local Model (Ollama) | `/v1/health` (`ollama` field) | ⚠️ Display-only (OFFLINE expected) |
| — | Agent history | `/api/agent/history` | ❌ STUB (hardcoded empty) |
| — | Agent memory search | `/api/agent/memory/search` | ⚠️ 500 risk (missing tool key) |

---

## 7. Prioritized Implementation Backlog

| Priority | Item | Effort | Risk | File(s) |
|----------|------|--------|------|---------|
| **P0** | Normalize probability model (softmax + backtest gate) | M | Med | `form_analyzer.py`, `analyzer.py`, `strike_tips.py:255` |
| P1 | Wire HUD bet execution behind `paper_mode` | S | Low | `RaceCard.tsx`, `api-prefixes.ts`, `App.tsx` |
| P1 | Make `/api/healing/pulse` real or honest | S | Low | `routes/healing.py:106` |
| P1 | Back `/api/agent/history` with real memory | S | Low | `routes/agent.py:27` |
| P2 | Guard 500-prone endpoints | S | Low | `betting.py`, `racing.py`, `agent.py` |
| P2 | Fix `agent/memory/search` None-guard | XS | Low | `routes/agent.py:47` |
| P3 | Remove dead `/mcp` WS proxy + fix `/contact` route | XS | Low | `middleware.ts`, `vite.config.ts`, `Footer.tsx`, `App.tsx` |
| P3 | Mark `AUTONOMY_PLAN.md` stale | XS | — | `AUTONOMY_PLAN.md` |

*Effort: XS < 1h, S < 3h, M < 1d.*

---

## 8. Recommended Next Step

Implement **P0 (§2.3)** — it is the only change that makes the system's core value proposition (finding real edge) mathematically sound. I can implement the softmax normalization + backtest gate now, keeping `paper_mode` so nothing live is affected.
