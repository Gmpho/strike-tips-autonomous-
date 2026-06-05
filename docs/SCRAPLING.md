# Scrapling

## Role in This Project

Scrapling is the primary web scraping library used by the racing parsers. It provides two fetcher tiers and a self-healing CSS selector engine.

## Fetcher Tiers

### Tier 1: `StealthyFetcher` (Headless Chromium + Cloudflare Bypass)
- **File:** `core_agent/skills/parsers/attheraces_api.py`
- Solves Cloudflare challenges via headless Chromium (Playwright)
- Uses a persistent user data directory for cached sessions
- Disables images/styles/fonts for performance
- 2 retries on failure

### Tier 2: `Fetcher` (HTTP Impersonation via `curl_cffi`)
- **Files:** `core_agent/skills/parsers/attheraces_api.py` + `core_agent/skills/parsers/racing_odds_api.py`
- Impersonates Chrome 131 TLS fingerprint
- Faster and lighter than headless browser
- No JavaScript execution

## Selector Engine

Both parser files use `scrapling.parser.Selector`:

```python
from scrapling.parser import Selector

tree = Selector(html, auto_save=True, adaptive=True)
tree.css("selector", adaptive=True)
```

- `auto_save=True` — caches parsed structure for debugging
- `adaptive=True` — self-healing selectors that survive minor HTML changes

## Files Using Scrapling

| File | Fetcher | Selector Features |
|------|---------|-------------------|
| `core_agent/skills/parsers/attheraces_api.py` | `StealthyFetcher` (Tier 1) + `Fetcher` (Tier 2 fallback) | `adaptive=True` |
| `core_agent/skills/parsers/racing_odds_api.py` | `Fetcher` only | basic CSS selection |

## Dependencies

- `requirements.txt`: `scrapling>=0.4.8`
- Requires Chromium installed via Playwright (for `StealthyFetcher` only)
