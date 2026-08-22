# 📡 Live Ops — Engine Telemetry Stream

Real-time visibility into the background engines that power Strike Tips: the Swarm Researcher, News RAG pipeline, Dreaming Engine heartbeat, and the Governor risk gate.

**HUD location:** sidebar → **📡 Live Ops** (dedicated tab, same pattern as News)

---

## Architecture

```
Swarm Researcher ──┐
News Poller ───────┤   emit(engine, message)
Dream Heartbeat ───┼──────────────────────────► core_agent/core/telemetry.py
Governor (DSI) ────┘                              │
                                                  │  in-memory ring buffer (100 events)
                                                  │  + best-effort Redis fanout
                                                  ▼
                                    agent:telemetry (Redis pub/sub channel)
                                                  │
                                                  ▼
                        GET /api/monitoring/stream → SSE event: telemetry
                        GET /api/telemetry        → REST hydration (newest-first)
                                                  │
                                                  ▼
                        DataBridge → hudStore.telemetry (capped 30)
                                                  │
                                                  ▼
                        Live Ops tab: engine cards + activity stream
```

### Design principles

1. **One connection** — telemetry rides the existing `/api/monitoring/stream` SSE (already in `SAFE_PATHS`; `EventSource` can't send custom headers). No duplicate EventSource connections from view components.
2. **Zero cost, zero disk** — events live in a memory deque (`MAX_EVENTS = 100`). Redis fanout is best-effort; failures are silently degraded (buffer-only still works).
3. **Never raises** — `emit()` is safe to call from sync or async contexts anywhere in the codebase; fanout runs as a fire-and-forget task.

---

## Event Schema

```typescript
interface TelemetryEvent {
  ts: number;      // unix seconds
  engine: 'swarm' | 'news' | 'dream' | 'governor' | 'system';
  badge: string;   // display label, e.g. "SWARM SCANNING"
  message: string; // ≤300 chars
}
```

## Emit points

| Engine | Source | Example event |
|--------|--------|---------------|
| 🟢 `swarm` | `backfill_form_insights()` | "🐝 Form backfill: 482 runners tracked, 6 web-grounded this cycle" |
| 🔵 `news` | `poll_news()` | "📰 4 new stories (80 cached) — BBC/Guardian/Mirror" |
| 🔵 `news` | `_link_news_to_insights()` via `poll_news()` | "🏷️ 12 stories linked to racecards in learning memory" |
| 🟣 `dream` | heartbeat tick (`heartbeat.py`) | "🌀 York R4 — What if the going turned Heavy? → shift +6.2%" |
| 🟠 `governor` | `_cache_dsi()` in `BankrollGovernor.calculate_max_stake` | "⚖️ DSI Stake Adjusted @ york:4: stress 42% → sizing ×0.75" |

The Governor also persists last-computed DSI per track:race to `data/dsi_cache.json` (capped at 200 most-recent entries). Snapshot enrichment stamps `event.dsi` onto every matching race, which drives the **DSI stress chip** on RaceCards:

| DSI (share of adverse dream scenarios) | Chip | Sizing effect |
|---|---|---|
| < 20% | 🟢 low stress | Full Half-Kelly (×1.0) |
| 20–50% | 🟠 moderate | ×0.75 |
| > 50% | 🔴 high stress | Quarter-Kelly (×0.50) |

---

## Backend API

### `GET /api/telemetry` (in `SAFE_PATHS`)
```json
{ "events": [ { "ts": 1787406837.09, "engine": "news",
                "badge": "NEWS RAG",
                "message": "📰 2 new stories (80 cached) — BBC/Guardian/Mirror" } ] }
```
Newest-first, max 30.

### `GET /api/monitoring/stream` (SSE)
Emits `event: telemetry` whenever new events land in the buffer — payload is an array of only the *fresh* events since the client's last count. Same connection also carries `snapshot`, `market-movers`, `predictor`, `results`, and `news`.

---

## Frontend flow

- **`DataBridge`** owns all transport: REST hydrates on start (`hydrateFeeds()`), then the SSE `telemetry` listener merges fresh events into `hudStore.telemetry` (deduped by engine+message+ts, capped 30).
- **`TelemetryView.tsx`** (sidebar → 📡 **Live Ops**) renders:
  - Four **engine cards** — Swarm Researcher / News RAG / Dreaming Engine / Governor — each showing Active (pulsing dot) or Idle, relative timestamp ("3 mins ago"), and its latest message. Engines that haven't reported yet render as dimmed Idle cards.
  - A chronological **Activity Stream** of every recent event with clock timestamps.
- The Agent Pipeline widget remains untouched — Live Ops is a dedicated tab, not an injection into existing widgets.

---

## Testing

`core_agent/tests/test_telemetry.py` — ring buffer ordering, default/custom badges, message truncation, MAX cap eviction, newest-per-engine lookup, no-running-loop safety, clear().

`core_agent/tests/test_news_linking.py` — horse-name matching, course fallback, region extraction, short-name guard (<5 chars never matched), duplicate-id dedupe within a call, seen-path persistence across calls.

Run locally: `pytest core_agent/tests/test_telemetry.py core_agent/tests/test_news_linking.py -v`
Run in Docker: `docker exec strike-bot-new pytest core_agent/tests/test_telemetry.py core_agent/tests/test_news_linking.py -v`

---

*Added: August 22, 2026 · Version v10.3 PRO / sw v2.5.0*
