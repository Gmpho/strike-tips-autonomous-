## Why

Strike Tips is a large 3-layer AI system (Cloudflare edge → Modal backend → Vercel HUD) with rich behaviour but **no OpenSpec behavioural contract yet** — `openspec/specs/` is empty. Before any feature can be added or archived feature-by-feature, the foundational capability must be captured: the value-bet detection and bankroll-discipline engine that every other feature (news, telemetry, dream engine, swarm researcher) hangs off of.

## What Changes

- Introduce the project's **first OpenSpec capability** `core-value-bet-analysis`, codifying the existing value-bet engine as a durable behavioural contract (naturally: no behaviour is introduced that isn't already implemented in `core_agent`).
- Capture as requirements: probability-edge value detection, the 5% edge threshold, hallucination-safe value validation, the never-assume-price auto-bet odds resolution, Half-Kelly stake sizing scaled by Dream Stress Index (DSI), hard bankroll circuit breakers, and bet recording/settlement including paper mode.
- Pin the invariants so subsequent features spec and test against a stable baseline.

## Capabilities

### New Capabilities
- `core-value-bet-analysis`: Baseline contract — how a candidate is judged a value bet, how its stake is disciplined by the governor, and how bets are recorded/settled. Each behaviour becomes a SHALL requirement in this capability's spec.

### Modified Capabilities
- None — this is the first capability; `openspec/specs/` is empty.

## Impact

- **Backend (existing code, now specced):** `core_agent/core/strike_tips.py` — value-bet validation (`_validate_value_bets`, fuzzy `difflib` cutoff 0.6), auto-bet odds resolution (`resolve_auto_bet_odds`), orchestrator `StrikeTips`. `core_agent/skills/bankroll_manager/governor.py` — `BankrollGovernor` (edge gate, Kelly/DSI sizing, circuit breakers, atomic persistence).
- **Contracts observable over APIs:** `/api/betting/*` (place/settle/history/account-summary) and the edge/Kelly endpoints rely on these invariants.
- **Tests (verification battery):** `core_agent/tests/test_governor.py`, `test_dsi_staking.py`, `test_auto_bet_odds.py`.
- **No schema/data migration; no frontend change** in this capability.