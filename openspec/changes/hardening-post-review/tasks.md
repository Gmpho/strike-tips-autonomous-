# Tasks: Post-Review Hardening

## 1. Corrupt-wipe guard

- [x] 1.1 `_load_state` flags corrupt files; `_save_state` refuses flagged state; verify new tests green
- [ ] 1.2 Repair path documented (restore from backup branch)

## 2. /v1 inbound auth

- [x] 2.1 Proxy checks X-API-KEY/session before upstream; verify 401 test + no spend
- [x] 2.2 Confirm HUD sends the key on /v1 calls already (or add it)

## 3. Pattern-5 bound

- [x] 3.1 Sentence-bound pattern 5; fuzzy confidence capped below 1.0; verify tests

## 4. Honest DSI

- [x] 4.1 Beta-prior smoothing + minimum-n floor; non-qualifying reads labeled heuristic; verify tests

## 5. Continuous reconciliation

- [x] 5.1 Scheduled JSON-vs-Postgres compare + Telegram drift alert; verify test with fakes

## 6. Ship

- [ ] 6.1 Full suite green (docker), commit, push, deploy on approval
