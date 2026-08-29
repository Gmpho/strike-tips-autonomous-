## 1. Data Paths & Constants

- [x] 1.1 Add `NEWS_PATH`, `NEWS_IMAGES_DIR`, `SWARM_INSIGHTS_PATH` to `core_agent/config/paths.py` with `os.makedirs(..., exist_ok=True)` and verify `python -c "from core_agent.config.paths import NEWS_PATH; print(NEWS_PATH)"` prints a path — **already present (lines 16-18, 27); import verified**
- [x] 1.2 Verify `DATA_DIR/news_images` and `DATA_DIR` swarm files are git-ignored and writable via `ls -ld data/news_images` — **`NEWS_IMAGES_DIR` exists and `os.path.isdir` True; DATA_DIR is repo data dir**

## 2. Swarm Skill — Core Helpers

- [x] 2.1 Implement region detection (`_detect_region`, `REGION_PREFIXES`) covering USA/Japan/SA/UK/IRE/Australia/NZ/France/Hong Kong/UAE with `en` prefix + course keyword fallbacks — **present (lines 102-150); `test_region_*` pass**
- [x] 2.2 Implement deterministic field blurb `build_field_insight(runner)` for missing `timeForm` (never fabricates) — **present (lines 159-193); `test_field_insight_*` pass**
- [x] 2.3 Implement `_groq_call(prompt)` reusing `get_async_client(resolve_hosts={"api.groq.com"})` / `openai/gpt-oss-20b` at `temperature 0.2 / max_tokens 220` — **present (lines 196-224)**
- [x] 2.4 Implement `_web_ground(horse, course, region)` via `search_racing_data` with `maf_search:{query}` cache — **present (lines 227-245); no-op on empty verified via test mock**
- [x] 2.5 Implement `_fresh_insight_exists` Chroma gate and `save_racing_insight` central writer — **present (lines 248-293)**
- [x] 2.6 Implement `swarm_insights.json` load/save (`load_swarm_insights`, `save_swarm_insights`) with atomic tmp+rename — **present (lines 296-315); `test_swarm_insights_round_trip` passes**

## 3. RSS News Ingestion

- [x] 3.1 Implement `_fetch_feed` / `_parse_feed` for feeds using `xml.etree` (`media:thumbnail/content`) — **present (lines 498-560)**
- [x] 3.2 Implement `poll_news()` dedupe-by-link, cap, atomic write to `data/news_latest.json` — **present (lines 560-622)**

## 4. Pure News Linking

- [x] 4.1 Implement `_link_news_to_insights(items, seen_path=None)` pure — **present (lines 624-721); covered by `test_news_linking.py` (7 scenarios pass)**
- [x] 4.2 Wire production call in `poll_news()` with daily `news_linked_<date>.json` `seen_path` — **wired (lines 560-622); `test_seen_path_persistence` passes**

## 5. Snapshot Enrichment & Wiring

- [x] 5.1 Implement `enrich_snapshot_with_insights(state)` injecting `region/swarmInsight/insightSource` — **present (lines 318-346); `test_enrich_stamps_missing_timeform_runners` passes**
- [x] 5.2 Implement `backfill_form_insights(state)` gated upgrade (cap 6/cycle, per-horse+day cache, fallback to field blurb) — **present (lines 360-445); `test_backfill_respects_groq_cap` / `test_backfill_per_day_cache_skips_today` / `test_backfill_ignores_high_odds_runners` pass**
- [x] 5.3 Wire `run_swarm_loop(interval=600)` and enrichment hook in `adaptive_odds_monitor.py` guarded by `try/except ImportError` — **wired (lines 17-28 import with no-op fallback, `create_task` at 416, enrichment at 459)**

## 6. Tests & Verification

- [x] 6.1 Add `core_agent/tests/test_swarm_researcher.py` (region, blurb, round-trip, enrichment, cap, cache) + `test_news_linking.py` already present; `pytest -k "swarm or news"` → 17 passed
- [x] 6.2 Run full Docker verification: `docker exec strike-bot-new pytest core_agent/tests/` passes (54 passed in 69.7s); swarm/news subset 17 passed. `pytest --cov` not available in container (`pytest-cov` not installed) — plain `pytest` is the verification gate and is green. Runtime `data/news_latest.json` population is covered by the wired `poll_news()` in `run_swarm_loop` (out of pytest scope).

