# Proposal: Honest Scraper Clients

## Why
Every outbound scraper request went through `http_client._build_session()`,
which always set a **random browser TLS impersonation**
(`proxy_manager.get_impersonate()` → chrome131/chrome124/safari17/firefox135),
and two parsers forced `impersonate="chrome131"` directly. ATR also sent a
fake Chrome `User-Agent` over httpx. Presenting a browser fingerprint while
not being a browser is deliberate evasion, not scraping: it has no innocent
explanation in an audit and it rots with every Chrome release.

`core_agent/config/compliance.py` claimed to be the compliance layer but was
imported by nobody — and it literally instructed "rotate identity" and "wipe
browser profile". It documented behaviour we should not have.

## What changes
- `compliance.py` rewritten as an enforced policy module:
  - honest `User-Agent` (`strike-tips/1.0 (+https://strike-tips-hud.pages.dev)`,
    override via `SCRAPER_UA`)
  - per-host pacing (`betway 5s`, `tab/4racing/raceform 3s`, unlisted 2s)
  - deny list via `SCRAPER_DENY_HOSTS` (suffix-matched)
  - TLS impersonation off by default; `SCRAPER_IMPERSONATE` opts in **and logs
    a warning naming it as evasion**
- `http_client.py` returns `PolicySession` / `AsyncPolicySession` that apply
  the honest UA and reserve a per-host request slot before every call.
- `proxy_manager.py` loses `BROWSERS` / `get_impersonate()` — the "rotate
  identity" machinery is gone. Proxy pool stays (explicitly configured).
- `racing_odds_api.py` and `attheraces_api.py` drop hardcoded `chrome131`.
- ATR's fake Chrome UA replaced with `user_agent()`.

## What this does NOT change
- It does not make automated access permitted by Betway/TAB/Raceform terms.
  It removes the adversarial parts (fingerprint spoofing, bursts, fake UA).
- ATR stays out of scope and circuit-broken; no work is done to defeat its
  bot protection.

## Verification
`core_agent/tests/test_honest_clients.py` (11 tests): honest UA, opt-in
warning, pacing, deny list, per-host isolation, sessions carry
`impersonate=None`.
