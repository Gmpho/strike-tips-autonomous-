# Free-Tier Web Search Cascade (Sep-2026)

> Privacy: no API keys, key values, or sheet IDs in this file.

## Why
Brave search needs money. Edge chat and the agent research loop had no
working web search. Tavily (1000 free credits/mo) + Exa (~1400/mo) now
carry both, with DDGS + page fetch as the free floor.

## How it works
- **Edge** (`web_search_racing` MCP tool): Tavily → Exa → Brave(legacy).
  Monthly spend tracked in KV (`search:budget:YYYY-MM`); exhausted
  providers are skipped, never billed.
- **Backend** (`search_racing` in `core_agent/skills/search_service.py`):
  Tavily → Exa → DDGS → SA-site fallback. File-backed monthly meters
  (`data/search_budget.json`), 40/day shared cap, 6h identical-query
  cache — loops cost zero while chat agents keep credits.
- Any model benefits (tool layer, not model layer): edge chat
  (Gemini/Groq auto-router, Ollama), `search_racing_data` specialist
  tool, settlement/grounding lookups.

## Secrets map
| Key | Local `.env` | Modal secret | Pages secret | Worker secret |
|---|---|---|---|---|
| `TAVILY_API_KEY` | yes (gitignored) | `strike-tips-search` | yes | yes |
| `EXA_API_KEY` | yes (gitignored) | `strike-tips-search` | yes | yes |

Rotate via dashboards on exposure; re-run the three secret commands;
no code change needed.

## Verification (all live Sep-2026)
- Direct API 200s for both providers; edge MCP returns
  `provider: tavily` with results; backend tests green
  (`test_search_providers.py`: cascade order, budget skip, cache hit,
  daily cap).
