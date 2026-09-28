# Tasks: Free-Tier Search Cascade

## 1. Edge worker

- [x] 1.1 Add `TAVILY_API_KEY`/`EXA_API_KEY` to Env and cascade helper with KV meters; verify `web_search_racing` returns `provider: "tavily"` live
- [x] 1.2 Set worker secrets (stripped values) and verify live MCP call

## 2. Backend

- [x] 2.1 Add `_tavily_search`/`_exa_search` + file meters + 40/day cap + 6h cache to `search_service.py`; verify direct 200s
- [x] 2.2 Add mocked tests (`test_search_providers.py`: order, budget skip, cache hit, daily cap) and verify green
- [x] 2.3 Attach `strike-tips-search` secret to Modal functions

## 3. Docs & housekeeping

- [x] 3.1 Write `docs/SEARCH_CASCADE.md` (no keys/values) and verify no secrets present
- [x] 3.2 Write `docs/X_POSTS_PARKED.md` revisit trigger and verify committed
- [x] 3.3 Validate change (`openspec validate free-tier-search-cascade)
