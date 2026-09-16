## 1. Dream scoring ledger (tonight)

- [ ] 1.1 `dream_ledger.jsonl` append in both dream paths (fav/odds/implied/predicted/family/date)
- [ ] 1.2 `settled_winners.jsonl` append in single-settle branches
- [ ] 1.3 `calibrate_dreams()` job + `dream_calibration.json`; unit tests with fixtures
- [ ] 1.4 Deterministic Tier-1 shift (remove random fallback when no insight)

## 2. Enriched dream inputs (tonight)

- [ ] 2.1 Betfair briefs + D1 recent results into `_groq_insight`; shift math reads combined text

## 3. Groq cuts (tonight)

- [ ] 3.1 `llm_cache.py` (date-scoped prompt hash store) wired into scan + dream paths
- [ ] 3.2 Batched scan analysis (6–8/call, single fallback); tests with stubbed provider

## 4. Verify (tomorrow morning)

- [ ] 4.1 Full suite green; Modal deploy; ledger + cache files appear on volume
- [ ] 4.2 Scheduling (03:00 sweep + bet-race top-ups) + 429 failover verification
- [ ] 4.3 Archive change + commit + push
