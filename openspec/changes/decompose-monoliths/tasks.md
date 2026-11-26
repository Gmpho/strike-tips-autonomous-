## 1. Baseline and characterisation (no production code moved)

- [ ] 1.1 Inventory every import of a private helper from `adaptive_odds_monitor` and `strike_tips` across production and tests; verify the list is recorded in `design.md` or a spec appendix and matches a fresh grep.
- [ ] 1.2 Inventory every edge route (path, method, auth, status, CORS) and KV key; verify the list is committed as a testable fixture.
- [ ] 1.3 Capture a recorded-cycle snapshot fixture for before/after comparison; verify a new test asserts field-for-field equivalence of events, prices, form and status flags.
- [ ] 1.4 Add add-only characterisation tests for facade re-export expectations; verify `docker exec strike-bot-new python -m pytest core_agent/tests/ -q` is fully green.

## 2. Off-time and card-hygiene extraction from the odds monitor

- [ ] 2.1 Create the dependency-free time/hygiene helper module with verbatim off-time, expiry, outage-clock and course/number normalisation logic; verify it imports standalone with no network, volume or scheduler side effect.
- [ ] 2.2 Re-export every moved symbol from `adaptive_odds_monitor`; verify all existing monitor and snapshot tests pass unchanged in Docker.
- [ ] 2.3 Add a test proving a patched path/time on the facade is honoured by the helper; verify it fails if the helper reads its own module constant.
- [ ] 2.4 Point `snapshot_writer` at the new dependency-free module; verify cold imports succeed and no circular import appears.

## 3. Fallback merge and spine extraction

- [ ] 3.1 Create the fallback/spine helper module with verbatim disk-cache, TTL, name-overlap and spine logic; verify standalone import.
- [ ] 3.2 Re-export all moved symbols from the monitor facade; verify every fallback and spine test passes unchanged.
- [ ] 3.3 Make disk path and clock explicit helper arguments passed by the facade; verify the patch-injection test from 2.3 also covers this module.
- [ ] 3.4 Compare a recorded cycle's published snapshot before and after the move; verify no priced runner, form field or rating changes.

## 4. ATR freshness extraction

- [ ] 4.1 Create the ATR helper module with verbatim freshness, lull, capture and merge logic; verify standalone import.
- [ ] 4.2 Re-export all moved symbols from the monitor facade; verify all ATR tests pass unchanged in Docker.
- [ ] 4.3 Assert the ATR helper module does not import the orchestrator at module scope; verify with a static import check.

## 5. Scan, exotic and value extraction from `strike_tips`

- [ ] 5.1 Create the scan-input helper module (PDF/tips text, TAB programs, live odds hydration, non-runner detection); verify standalone import and no side effects.
- [ ] 5.2 Create the exotic helper module (pool legs, dividends, validation, history, play construction); verify all exotic tests pass unchanged.
- [ ] 5.3 Create the value helper module (jurisdiction, text/horse normalisation, auto-bet odds, value validation, meeting gates); verify all value/selection tests pass unchanged.
- [ ] 5.4 Keep `StrikeTips` methods as thin delegators with unchanged signatures; verify every `StrikeTips.*` caller and test passes unchanged.
- [ ] 5.5 Compare a recorded daily-scan snapshot before and after; verify identical picks, prices and off-times.

## 6. Worker router split and honest diagnostics

- [ ] 6.1 Add a route-parity test covering every REST/MCP path, method, auth rule and CORS header; verify it passes before any move.
- [ ] 6.2 Move route handlers into focused modules while `index.ts` remains the single router and `export default`; verify route-parity test, `npm test` and `npx tsc --noEmit` all pass.
- [ ] 6.3 Centralise upstream block text into a diagnostics module that names the real refusing layer, status and colo; verify a test asserts no stale "cron is production fetch" string remains.
- [ ] 6.4 Assert the traffic-triggered refresh still fires only on full-card requests, with the 8-minute throttle, and the hourly cron still registered; verify KV write estimate stays below the free-tier cap.
- [ ] 6.5 Verify no API key or token appears in any response, log or diagnostic produced by the split modules.

## 7. Integration, documentation and release

- [ ] 7.1 Run the full Docker suite and record the exact pass/skip/fail line; verify zero failures attributable to this change.
- [ ] 7.2 Run `npm test` and `npx tsc --noEmit` in `cloudflare_mcp_edge/`; verify both clean.
- [ ] 7.3 Probe live card, `/picks` race feed and edge KV keys; verify no regression in priced counts or staleness labels versus the pre-change baseline.
- [ ] 7.4 Update `openspec/project.md` and the repo docs with the new module map and facade policy; verify paths in docs match files on disk.
- [ ] 7.5 Deploy only on explicit user request (Modal for Python, Wrangler for the Worker); verify deployed version IDs and a post-deploy live probe, with rollback to the previous commit available.
