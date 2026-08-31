## Context

The value-bet engine is fully implemented in `core_agent` and drives the `/api/betting/*` and edge/Kelly endpoints. This change does **not** add runtime behavior — it codifies the existing engine as the project's first OpenSpec capability so later features (news, telemetry, dream engine, swarm researcher) have a stable behavioral baseline to build against. The `openspec/specs/` tree is currently empty; this capability establishes the flat layout convention.

## Goals / Non-Goals

**Goals:**
- Produce a machine-readable, validatable behavioral contract for value detection and bankroll discipline.
- Keep the contract aligned one-to-one with the existing implementation invariants (edge gate, half-Kelly × DSI, circuit breakers, atomic recording, never-assume-price auto odds).
- Make the scenarios map to the existing verification battery (`test_governor.py`, `test_dsi_staking.py`, `test_auto_bet_odds.py`) so tests double as living verification of the contract.

**Non-Goals:**
- No new runtime behavior, refactor, or change to governor constants.
- No frontend or API-surface change.
- No migration of existing data; the bet history/bankroll state files stay unchanged.

## Decisions

- **Single flat capability path** `core-value-bet-analysis`. The project had no spec domains yet; the flat layout (matching the `swarm-researcher` capability style already proposed) is the established convention, so no new domain level is introduced.
- **Spec boundaries, not classes.** Requirements describe externally observable behavior (a bet is placed/blocked, a price is resolved/refused, a stake is capped) rather than internal functions, so future refactors don't invalidate the contract.
- **Auto-bet odds resolution as a hard requirement.** `resolve_auto_bet_odds` returning `None` on a missing/≤1.01 price (never an assumed default) is called out explicitly because an invented price would corrupt stake sizing, settlement, and learning stats — the highest-risk invariant to pin.
- **DSI buckets as a spec-level invariant.** The 1.0 / 0.75 / 0.50 scale mapping to the <20% / 20–50% / >50% stress bands is behavior downstream systems (HUD stress chips, telemetry) rely on, so it belongs in the spec.

## Risks / Trade-offs

- Codifying current behavior freezes today's thresholds. Any future change to a governor constant (e.g. edge 5.0, Kelly 0.5, limits 5/20/50) becomes a MODIFIED spec in a later change — which is the intended feature-by-feature process rather than a defect.
- The contract is only as good as its tests. We accept the existing battery as the verification source of truth; if a scenario isn't covered by a current test, a follow-up test is called out in tasks.