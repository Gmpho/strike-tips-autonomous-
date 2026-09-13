## 1. Push helper + callers

- [x] 1.1 `cf_push.py` (single-key, 401 retry, never raises) + 10 tests
- [x] 1.2 Monitor both push sites use helper; scan mirrors cards; settle mirrors results
- [x] 1.3 Modal deployed; full suite 183 green

## 2. Worker KV budget

- [x] 2.1 Single-put + write-gate; per-track reads filter full snapshot
- [x] 2.2 Deployed; root cause proven via debug detail (put limit exceeded)

## 3. Verify (after UTC midnight quota reset)

- [ ] 3.1 KV `odds:full_snapshot` fresh + no ingest 500s
- [ ] 3.2 D1 row count grows on next scan/settle cycles
