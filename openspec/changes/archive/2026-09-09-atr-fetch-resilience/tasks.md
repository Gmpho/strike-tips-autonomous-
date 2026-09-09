## 1. Packaging: make every tier importable everywhere

- [x] 1.1 Pin `patchright>=1.0.0` in `requirements.txt` and `patchright==1.62.3` in `pinned-requirements.txt`; verify `from scrapling.fetchers import Fetcher, StealthyFetcher` succeeds on Modal (diag run)
- [x] 1.2 Pre-download Patchright Chromium in `Dockerfile`; install at `odds-monitor` boot in `Dockerfile.odds` CMD; verify `browser_profile` materializes on the volume
- [x] 1.3 Import `Selector` in an independent guarded block (`_SELECTOR_AVAILABLE`); dummy fallback only when truly absent; verify no `NameError` path remains

## 2. Fetch tiers (`attheraces_api.py`)

- [x] 2.1 Add `_is_challenge_page()` on size + content markers; explicitly document the beacon-tag post-mortem in the docstring
- [x] 2.2 Reorder tiers cheap-first (httpx → Fetcher → StealthyFetcher) with per-tier challenge rejection and a terminal WARNING
- [x] 2.3 Browser last resort: `solve_cloudflare=False` (Fastly, not CF), cookie-preserving reload, volume-shared 1/hour throttle (`.atr_stealth_last`)
- [x] 2.4 Raise fetch budgets to 150s (results/movers/predictor) and cron timeout to 900s with `memory=1024`

## 3. Cadence (`adaptive_odds_monitor.py`, `modal_app.py`)

- [x] 3.1 Add `_atr_snapshot_fresh()` (45-min all-files gate) and `_atr_file_fresh()` (per-file gate); apply to both `run_single_cycle()` and the `run()` loop (fixing an inverted guard found in review)
- [x] 3.2 Refresh the `cloudflare-mcp` Modal secret (new key + URL) to unblock snapshot push 401s

## 4. Verification

- [x] 4.1 Tier-by-tier Modal diags: challenge vs full pages, per-tier sizes, profile creation
- [x] 4.2 Manual monitor cycles to recovery: results 525 races/23 meetings, predictor 51, movers 579
- [x] 4.3 Staleness warnings clear; prod `/results`, `/predictor`, `/market-movers` flowing (369 races, 945 runners)
- [x] 4.4 Document the `_fs-ch-` post-mortem in code so the marker is never reintroduced
