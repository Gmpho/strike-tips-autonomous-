## 1. Codify the baseline spec

- [ ] 1.1 Create `proposal.md` in `openspec/changes/core-value-bet-analyzer/` and verify it describes the new capability `core-value-bet-analysis`
- [ ] 1.2 Write `specs/core-value-bet-analysis/spec.md` with all six ADDED requirements and their scenarios (edge detection, never-assume price, hallucination-safe validation, half-Kelly×DSI sizing, circuit breakers, recorded/settlement) and verify each scenario uses exactly `####`
- [ ] 1.3 Write `design.md` and `tasks.md` describing approach and steps
- [ ] 1.4 Confirm the spec opens with a `## Purpose` section (new capability)

## 2. Verify the contract against the implementation

- [ ] 2.1 Confirm `resolve_auto_bet_odds` returns `None` (never an assumed price) for missing/non-numeric/≤1.01 prices — see `core_agent/core/strike_tips.py`
- [ ] 2.2 Confirm governor constants match the spec: edge 5%, Kelly 0.5, per-bet 5%, daily 20%, drawdown 50%, DSI buckets 1.0/0.75/0.50 — see `core_agent/skills/bankroll_manager/governor.py`
- [ ] 2.3 Confirm `_validate_value_bets` uses exact + fuzzy (0.6) matching and discards unmatched candidates — see `core_agent/core/strike_tips.py`
- [ ] 2.4 Run the verification battery and confirm all pass: `pytest core_agent/tests/test_governor.py core_agent/tests/test_dsi_staking.py core_agent/tests/test_auto_bet_odds.py`

## 3. Validate the change

- [ ] 3.1 Run `openspec validate --change core-value-bet-analyzer` and confirm zero errors
- [ ] 3.2 Run `openspec validate --change core-value-bet-analyzer --strict` and confirm zero errors
- [ ] 3.3 Show final status with `openspec status --change core-value-bet-analyzer` and confirm all artifacts report `done`