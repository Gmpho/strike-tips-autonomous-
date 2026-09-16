## Why

Two pains converged: crossed-wire Telegram settles were untraceable by construction (no shared id across scan/settle/notify), and Modal logs are unqueryable plain text. Separately, AI chat rendered raw `### **` markdown, and routine fallback warnings buried real signals.

## What Changes

* Correlation IDs (`core_agent/core/correlation.py`): `scan-`/`settle-`/`chat-` bound at flow entry, tagged on key logs, trailing token on Telegram messages.
* Structured JSON logs on Modal (auto-detect via `MODAL_TASK_ID`, `LOG_FORMAT` override); human-readable locally.
* Levels honesty pass: routine fallbacks demoted (Betway/Betfair retries, DSI fallback, empty search, racing-odds timeouts, non-429 Groq failures); 429s + money-path failures stay warnings.
* AIChat renders assistant markdown (ReactMarkdown + GFM tables, theme-mapped elements).

## Capabilities

### New Capabilities
- `observability`: correlation IDs, JSON logging, level discipline.

### Modified Capabilities
- (none — additive only)
