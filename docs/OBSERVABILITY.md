# Observability — Correlation IDs, JSON Logs, Honest Levels

## Correlation IDs (`core_agent/core/correlation.py`)

One id per flow, bound at entry, threaded through logs + Telegram:

| Flow | Prefix | Bound at |
|---|---|---|
| Morning/midday scan | `scan-` | `StrikeTips.run_daily_scan` |
| Settlement run | `settle-` | `ResultTracker.check_and_settle_open_bets` |
| Chat turn | `chat-` | `handle_chat_completions` |

- Logs: `logger.info(f"{tag()} ...")` → `[settle-a1b2c3d4] ...`
- Telegram: `send_value_bet` / `send_bet_result` accept `ref=""`, rendered as a trailing `· id` token.
- Incident drill: copy the token from the Telegram message → grep Modal logs for it.
- Empty when unbound: tests, REPL, and uninstrumented paths never break.

## JSON logging (`core_agent/core/logging_setup.py`)

- Containers under `MODAL_TASK_ID` (or `LOG_FORMAT=json`) emit one JSON object per line: `{ts, level, logger, msg}`.
- Everywhere else keeps human-readable `HH:MM:SS LEVEL name: msg`.
- Wired into `modal_app` and `api_pkg` (idempotent — safe to call from any entry module).
- Override level with `LOG_LEVEL` (default `INFO`).

## Level discipline

- Routine/retried/handled → `info`/`debug`: Betway/Betfair retries, DSI fallback, empty searches, racing-odds timeouts, non-429 Groq failures, volume-reload skips.
- Stays `warning`: HTTP 429s (rate-limit signal), money-path failures (settle/void/cancel errors, stake-cap hits, delusion-gate rejects), state-load failures, cycle failures.
- Rule of thumb: a quiet overnight log where every warning deserves a look.
