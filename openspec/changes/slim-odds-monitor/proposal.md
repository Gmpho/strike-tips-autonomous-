# Proposal: Slim Odds Monitor (drop the browser stack)

## Why
The odds monitor never opened a browser. `adaptive_odds_monitor.py` imports
`BetwayAPI` (TrackRacing JSON) and `RacingOddsAPI` (HTML), yet the container
still shipped `playwright`, `patchright`, `scrapling`, Chromium plus its system
libraries (`install-deps chromium`), and reinstalled browsers at every boot
(`docker-compose.yml`, `Dockerfile.odds` CMD). The odds-monitor image is 3.58GB
for a workload that only needs HTTP + an HTML parser.

`scrapling` was the blocker: `racing_odds_api.py` and `attheraces_api.py`
imported its `Fetcher`/`StealthyFetcher`/`Selector`, and `patchright` is a hard
import dependency of `scrapling.fetchers`.

## What changes
- New `core_agent/core/html_selector.py`: bs4 + lxml adapter exposing the only
  three surfaces the parsers use (`css()`, `attrib`, `get_all_text()`), so ATR's
  ~900 lines of parsing stay untouched.
- `racing_odds_api.py`: scrapling → `httpx`-equivalent via the policy client +
  BeautifulSoup parsing.
- `attheraces_api.py`: scrapling imports gone. Tiers are now
  `httpx → paced curl_cffi client → circuit breaker`. **The StealthyFetcher tier
  is deleted** — solving Fastly/Cloudflare challenges is exactly the behaviour
  the honest-client change removes, and ATR is a UK/IRE backstop only.
- `requirements.txt` / `pinned-requirements.txt`: drop `playwright`,
  `patchright`, `scrapling`.
- `Dockerfile`, `Dockerfile.odds`, `docker-compose.yml`: remove Chromium
  installs, `playwright_cache` volume, and `browser_profile` mount.

## Expected effect
Image drops the Chromium binary (~500MB), its system deps, and the duplicate
Patchright build; boot no longer spends time on `playwright install`.

## Risks
- Selector behaviour: scrapling's `.css(adaptive=True)` self-healing is gone.
  Mitigated by `tests/test_html_selector.py` + the existing ATR course-context
  parsing test, which now runs against the adapter instead of skipping.
- ATR parsing itself is unverified against live HTML (site blocks us); it is a
  settlement backstop, and the breaker keeps it quiet either way.
