## Why

The system has accumulated several 1,000–4,000 line files in which unrelated
concerns share one namespace: `adaptive_odds_monitor.py` (2,963 lines) mixes
off-time maths, fallback merges, ATR freshness gates, feed health and the cycle
loop; `strike_tips.py` (3,982 lines) mixes PDF/tips parsing, exotic pools, live
odds hydration and daily scans; `cloudflare_mcp_edge/src/index.ts` (993 lines)
hosts every REST route, MCP tool and cache path. That coupling is how a small
edit to a price merge silently changes settlement or feed-health behaviour —
the class of bug that produced the 26 Nov price flapping and the false "403"
diagnostics. Extracting pure helpers behind thin orchestrators makes each
concern independently testable before the next optimisation pass.

## What Changes

- Split the two Python monoliths into a thin orchestrator plus focused helper
  modules (`odds_time`, `fallback_merges`, `atr_freshness`, `feed_health`,
  `scan_inputs`, `exotic_analysis`, `value_analysis`), keeping the original
  modules as import-compatible facades.
- Split the Worker's single `index.ts` into a small router/orchestrator plus
  route and diagnostics modules; keep all paths, status codes, CORS headers and
  bindings byte-for-byte compatible.
- Make upstream-block diagnostics truthful: name the layer (Betway / SportyBet /
  Cloudflare WAF), the colo when known, and never claim a retired path is the
  production fetch.
- Stage the work so every phase ends with a green Docker suite; add
  characterisation tests *before* moving code. No behaviour change to the
  published card, picks, ledger or settlement math.
- Out of scope (protected paths, unchanged without explicit approval):
  `core_agent/skills/result_tracker.py`, `core_agent/skills/bankroll_manager/governor.py`,
  `core_agent/api_pkg/__init__.py`, `core_agent/core/modal_app.py`,
  `strike-tips-hud/functions/`, and all existing tests (coverage only grows).
- Deferred to a follow-up change: `strike-tips-hud/src/components/AIChat.tsx`
  (1,423 lines) — kept out so this change stays reviewable.

## Capabilities

### New Capabilities
- `core-module-boundaries`: compatibility contract for extracting the odds
  monitor and strike-tips orchestrators — stable import surface, pure helper
  modules, single lifecycle owner, unchanged published output.
- `edge-route-boundaries`: compatibility contract for the Worker router split —
  route parity, unchanged bindings/CORS, preserved traffic-triggered fetch and
  KV write budget.
- `feed-diagnostics-honesty`: observable requirement that every upstream block
  report names the real layer/colo and no stale production-path claim is served
  to operators or the HUD.

### Modified Capabilities
- none — no existing spec's behavioural requirements change.

## Impact

- **Code:** `core_agent/core/adaptive_odds_monitor.py`, `core_agent/core/strike_tips.py`,
  `cloudflare_mcp_edge/src/index.ts`; new sibling modules in each layer.
- **Tests:** 14 test modules import private helpers from the two Python
  monoliths; those symbols must remain importable from the facade. New tests may
  be added, none deleted or weakened.
- **APIs / data:** none. Snapshot schema, `/api/*` routes, MCP tools, KV keys,
  D1 bindings and Modal cron schedules stay identical.
- **Rollout:** Python changes deploy to Modal, Worker changes via Wrangler —
  only after the Docker suite is green and only on explicit request.
