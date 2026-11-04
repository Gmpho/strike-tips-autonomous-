# Design: Composio Creation Tools

## Context
- Composio CLI authed (org workspace), `googlesheets` linked, Sheets slugs
  verified live (tabs created, headers written, rows appended + read back).
- Resend email leg proven separately; alerts stay on Resend (out of scope).
- Agent calls tools as plain Python functions via `TOOL_REGISTRY`
  (TaskRouter → specialist → registry). Providers: Ollama local, Groq/Gemini
  fallback. Groq ceiling 8k TPM.

## Goals
- Subscriber connects own Google/X once (Connect Link), agent acts under
  *their* connection thereafter.
- Agent surface stays at 3 fixed internal names; vendor slugs never reach
  models (tool-catalog token bloat + hallucinated-slug risk).
- Deterministic compute (PnL math) has zero model involvement.

## Decisions
- **For You CLI execution** (`composio execute` subprocess, JSON in/out),
  not MCP gateway (we run our own edge MCP; second gateway = moving parts)
  and not Platform SDK sessions (no per-user server sessions needed at
  this volume; revisit if subscriber count forces it).
- **Slugs discovered at runtime**, pinned after `--dry-run` + one live
  test each. Pinned set: `GOOGLESHEETS_ADD_SHEET`,
  `GOOGLESHEETS_VALUES_UPDATE`, `GOOGLESHEETS_VALUES_GET`,
  X post-create family (to discover).
- **Failure = fallback**: any Composio/Google/X error returns a plain
  string; agent delivers via Telegram + Email instead. X 402 (credits
  empty) pauses posting with a spending-limit alarm, never silent drop.
- **Spend**: per-user daily post cap in adapter; link-free posts only
  ($0.015) unless user opts into URL posts ($0.20) explicitly.

## Risks
- Composio Free cap pauses → adapter must surface, never hang (timeouts
  on every call) — covered by fallback rule.
- X credentials revoked mid-flow → error names the fix (re-link), agent
  relays it verbatim.
- Scope creep into alerts/digests → explicitly out; Resend owns alerts.
