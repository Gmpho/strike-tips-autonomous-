# Tasks: slim-odds-monitor

## 1. Parser layer
- [x] 1.1 Add `core_agent/core/html_selector.py` (bs4/lxml, scrapling-compatible surface)
- [x] 1.2 `racing_odds_api.py`: scrapling → policy client + BeautifulSoup
- [x] 1.3 `attheraces_api.py`: scrapling → adapter; Tier 2 uses policy client; Tier 3 stealth deleted
- [x] 1.4 Update ATR module docstring + fetch/results docstrings (no browser claims)

## 2. Dependencies
- [x] 2.1 Remove `playwright`, `patchright`, `scrapling` from `requirements.txt`
- [x] 2.2 Remove same pins from `pinned-requirements.txt`
- [x] 2.3 `Dockerfile`: delete `install-deps chromium` / Playwright / Patchright downloads
- [x] 2.4 `Dockerfile.odds`: delete Chromium install, scrapling cache link; CMD is plain python
- [x] 2.5 `docker-compose.yml`: drop `playwright_cache` volume + `browser_profile` mount + install-on-boot

## 3. Tests
- [x] 3.1 `tests/test_html_selector.py` — adapter surface + ported racing-odds parsing
- [x] 3.2 Remove `importorskip("scrapling")` from `test_atr_course_context.py` (premise changed: dependency retired)
- [x] 3.3 Suite: 565 passed (baseline 548), 2 known time-dependent failures, 4 fastapi-missing errors

## 4. Verification (user)
- [ ] 4.1 `docker compose build` both images; confirm odds-monitor image size drop
- [ ] 4.2 Boot odds-monitor and confirm a snapshot refresh with no Chromium errors
