# Tasks: honest-scraper-clients

## 1. Policy module
- [x] 1.1 Rewrite `core_agent/config/compliance.py` as enforced policy (UA, pacing, deny list, impersonation opt-in)
- [x] 1.2 Delete `COMPLIANCE_CONFIG` / `LEGAL_REQUIREMENTS` / `EMERGENCY_PROCEDURES` fiction

## 2. Client wiring
- [x] 2.1 `http_client.py`: `PolicySession` / `AsyncPolicySession`, honest UA, slot reservation
- [x] 2.2 `proxy_manager.py`: remove `BROWSERS` + `get_impersonate()`
- [x] 2.3 `racing_odds_api.py`: drop `impersonate="chrome131"`
- [x] 2.4 `attheraces_api.py`: drop `impersonate="chrome131"`, honest UA on httpx tier

## 3. Tests
- [x] 3.1 `tests/test_honest_clients.py` — 11 tests
- [x] 3.2 Parser/odds subset green on host
