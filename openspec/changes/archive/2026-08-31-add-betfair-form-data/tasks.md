## 1. Discovery: find the Betfair SA data source

- [x] 1.1 Probe betfairsa.co.za with Playwright network capture (or known API patterns) and document the endpoint(s) carrying racecard runner details (gear + last run) in `design.md` appendix; record request shape, auth/session needs, and response field names
- [x] 1.2 Decision gate: confirm reachable via plain `httpx` (Betway pattern) OR Playwright (odds-monitor pattern); if both fail, flip source to PDF Computaform fallback and record the decision — parser/merge/spec contract stays unchanged

## 2. Parser: `core_agent/skills/parsers/betfair_sa.py`

- [x] 2.1 Create `BetfairSA` class with `get_form_format() -> {events: {eid: {runners: [{name, gear, daysSinceRun}]}}}` and verify the file exists and imports cleanly (`python -c "from core_agent.skills.parsers.betfair_sa import BetfairSA"`)
- [x] 2.2 Implement gear normalization to canonical tokens (`·`-joined, title-cased passthrough for unknown tokens) and verify `"Hood/Tongue Strap/BLINKERS"` → `"Hood · Tongue strap · Blinkers"` in a unit test
- [x] 2.3 Implement `daysSinceRun` as non-negative int (absent/invalid → absent, never 0-by-default) and verify via unit test
- [x] 2.4 (HTML path NOT taken — clean JSON API confirmed in discovery, task N/A. Marked skipped per design.md decision.)
- [x] 2.5 Cache raw responses to `data/betfair_form_*.json` and verify the cache file is written on fetch

## 3. Merge: `adaptive_odds_monitor.py`

- [x] 3.1 Add `_merge_bf_into(state, bf_snapshot)` matching horses exact-first (whitespace/case-normalized) then `difflib.get_close_matches` 0.6, scoped per (track, race), one-to-one (matched Betfair runners excluded from later candidate pools); verify via unit test with exact, fuzzy, and no-match fixtures
- [x] 3.2 Fetch Betfair form on the monitor's slow cycle with last-good-cache reuse (bounded max-age); verify a failed fetch reuses cache before skipping
- [x] 3.3 Wrap fetch/parse/merge in tolerant error handling: failure → snapshot unchanged + `_write_healing_event()` logged; verify via unit test that a raising parser leaves the snapshot byte-identical except absent new keys and appends a healing event
- [x] 3.4 Verify partial coverage: snapshot with 3 races, Betfair covering 1 → covered runners gain fields, others untouched, single publish

## 4. HUD: types + RaceCard

- [x] 4.1 Add optional `gear?: string` and `daysSinceRun?: number` to `Runner` in `strike-tips-hud/src/types/index.ts` and verify `tsc` passes
- [x] 4.2 Add sortable **Days** column to RaceCard (sort key `daysSinceRun`, absent sorts last) and verify sort behavior in a unit test of the sort comparator
- [x] 4.3 Add gear badge rendering (normalized `·` tokens, absent → empty cell) and verify absent-field rendering produces no placeholder/error in a component test

## 5. Verification battery + validation

- [x] 5.1 Write hermetic tests: `tests/test_betfair_sa.py` (parser fixtures incl. normalization, days parsing, cache) and extend with merge tests (exact/fuzzy/no-match/partial/degradation+healing); verify `pytest core_agent/tests/test_betfair_sa.py` passes in Docker (`docker exec strike-bot-new pytest core_agent/tests/test_betfair_sa.py`) or via the strike-tips-base image mount
- [x] 5.2 Run the full backend battery and confirm no regressions: `pytest core_agent/tests/` → all pass
- [x] 5.3 Run HUD build: `npm run build` in `strike-tips-hud/` → tsc + vite build pass
- [x] 5.4 Validate the change: `openspec validate add-betfair-form-data` and `--strict` → zero errors
- [x] 5.5 Show final status `openspec status --change add-betfair-form-data` → all artifacts done, then mark all tasks complete and request archive review
