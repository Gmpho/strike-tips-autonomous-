# Production Hardening & Log Display Optimization

## What We Did

### Fixed Race Analysis Hallucinations
AI was generating fake horse names in `value_bets`. Fixed with `_validate_value_bets()` using `difflib` to cross-reference AI output against scraped runner names — mismatches get `[WARN]` rejected.

**Lesson:** Never trust LLM output for factual data. Always cross-reference against ground-truth sources.

### Fixed Notification Loss on Shutdown
`_fire_async()` scheduled coroutines on the event loop but `close()` killed the httpx client before they ran. Fix: track pending tasks in `_PENDING_TG_TASKS` and `drain()` them via `asyncio.gather()` before closing.

**Lesson:** When fire-and-forget tasks share a client lifecycle, you must explicitly drain pending work before teardown.

### Fixed Missing Await in Scheduler & Routes
`scheduler.py` and `routes/config.py` both had `await` missing on async `send_message` calls. Rustic syntax errors that caused silent failures.

**Lesson:** Async code needs disciplined code review — missing `await` is invisible at runtime.

### Made run_odds_monitor Persistent
Switched from `container.spawn()` (ephemeral) to `min_containers=1` (declarative, survives death). Started it via FastAPI lifespan as a background task.

**Lesson:** Modal `min_containers=1` is more reliable than `.spawn()` for daemon-like workers.

### Eliminated Telegram Alert Spam
Removed `global_value_bet` default alert (fired for every horse with odds >= 5.0). Added 120s rate limit on `_on_alert`. Batched non-critical alerts into a 30-min digest via new `AlertDigester`.

**Lesson:** Default alert thresholds in code can become spammy in production. Rate-limiting and batching are essential for notification sanity.

### Fixed Snapshot 500 Error
`app.state.snapshot_cache` was never initialized because `@app.on_event("startup")` is suppressed when `lifespan=` is passed to `FastAPI()`. All startup code had to move into the `lifespan()` context manager.

**Lesson:** FastAPI's `lifespan` and `on_event` are mutually exclusive. If you use `lifespan=`, ALL startup logic must go there — no leftovers.

### Fixed Stale Alert Config Persistence
Alerts were persisted to a Docker volume and survived code-only removals. Fixed: `_load_alerts()` now sanitizes any `condition_type == "value_bet"` from disk. `initialize()` calls `clear_history()` to wipe old triggered alert JSONL.

**Lesson:** Persistence is a cache invalidation problem. When you remove a feature from code, you must also handle stale persisted state.

### Added Alerts to HUD Snapshot
`/api/monitoring/snapshot` now injects last 20 triggered alerts from `alert_history.json` into the response so HUD users see them.

### Fixed WebGL Crash in HUD
Three.js `<Canvas>` crashed in headless/GPU-less environments. Fixed by feature-detecting `webglSupported()` before mounting, with a static gradient fallback.

**Lesson:** Three.js is not safe to render unconditionally in the browser. Always check WebGL support first.

### Reduced Frontend Polling Cost
13 parallel API calls every 5s = ~195 req/min hitting Modal. Split into `syncFast()` (5s: 4 endpoints) and `syncSlow()` (30s: 9 endpoints). Cost reduction ~70%.

**Lesson:** Not all data needs sub-10s freshness. Classify endpoints by update frequency and poll accordingly.

### Fixed Log File Backend
`log_setup.py` now adds `RotatingFileHandler` to root logger at startup. `/api/logs` endpoint returns file contents. Previously logs only went to stdout.

### Mapped Ollama ERROR to OFFLINE in UI
`useAgentHealth.ts` maps `'error'` state to `'offline'`; `AgentStatus.tsx` shows grey `OFFLINE` badge instead of scary red `ERROR`.

**Lesson:** User-facing status should use calming language. Internal error states are implementation details.

### AlertDigester — Batch Non-Critical Alerts
Created `AlertDigester`: queues `odds_drop`/`value_bet` alerts, flushes as one formatted digest every 30 minutes. Critical alerts (bet results, errors) bypass the queue. Wired into `AdaptiveOddsMonitor` and `StrikeTips`.

### Broadcast to All Authorized Users
`telegram_bot.py` rewritten with `broadcast()`: reads `whitelist.json`, sends to admin + every authenticated user. WhatsApp group members auth via `/auth <pin>` → added to whitelist → receive all broadcasts individually.

### Lazy AlertDigester Loop
`AlertDigester.start()` from sync code just sets a flag. `create_task` deferred to first async entry point or first `push()` call. Handles the `StrikeBrain.initialize()` called from sync code pattern.

### Smart Log Scrolling
`LogsView.tsx` had aggressive auto-scroll that janked to bottom on every update. Fixed with `isPinned` state: tracks if user scrolled up, only auto-scrolls when at bottom. "↓ Live" button appears when unpinned to snap back.

---

## Key Patterns & Principles

| Pattern | Applied In |
|---------|-----------|
| Cross-reference AI output against ground truth | `_validate_value_bets()` |
| Drain pending work before teardown | `_fire_async()` + `close()` |
| `lifespan` vs `on_event` exclusivity | `api.py` startup migration |
| Stale persisted state sanitation | `_load_alerts()` filter |
| Feature-detect before render | `webglSupported()` check |
| Polling frequency tiers | `syncFast` / `syncSlow` split |
| Batch don't broadcast (for non-critical) | `AlertDigester` (30-min digest) |
| User-facing status normalization | `error` → `offline` mapping |
| Respect user scroll position | `isPinned` in `LogsView.tsx` |

---

## Architecture Decisions

- **No Telegram group broadcast** — each user gets individual messages via `/auth <pin>`. Requires `broadcast()` to load whitelist from disk each call (not cached) so new auths are picked up immediately.
- **AlertDigester lazy start** — `start()` sets `_running=True` from sync code; `create_task` deferred to first async entry or `push()` call. Avoids event loop crashes when `StrikeBrain.initialize()` is called from sync context.
- **DIGEST_INTERVAL_SECONDS = 1800** (30 min) — tune if users want more frequent summaries.
