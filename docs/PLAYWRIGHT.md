# Playwright

## Role in This Project

Playwright's Chromium binary is a **runtime dependency of Scrapling's `StealthyFetcher`**, which wraps headless Chromium to solve Cloudflare challenges. It is not used directly in any production code.

## Usage

### Indirect (Production)
- `core_agent/skills/parsers/attheraces_api.py` — `StealthyFetcher` uses Playwright Chromium under the hood to fetch Cloudflare-protected pages from `attheraces.com`
- Playwright is **not imported** in any production Python file

### Direct (Utility Only)
- `discover_odds_api.py` — standalone script using `playwright.sync_api` to intercept network requests on Oddschecker (development/discovery tool, not part of runtime)

## Docker Setup

Both Dockerfiles install Playwright system deps and Chromium:

| Container | Dockerfile | CMD |
|-----------|------------|-----|
| `strike-bot` | `Dockerfile` | `RUN playwright install-deps chromium` / `CMD playwright install chromium && uvicorn ...` |
| `odds-monitor` | `Dockerfile.odds` | `RUN playwright install-deps chromium` / `CMD playwright install chromium && python ...` |

Three containers share a `playwright_cache` volume for the Chromium binary (`/root/.cache/ms-playwright`).

## Dependencies

- `requirements.txt`: `playwright==1.58.0`
- Chromium browser binary (~300 MB) installed at container runtime via `playwright install chromium`
