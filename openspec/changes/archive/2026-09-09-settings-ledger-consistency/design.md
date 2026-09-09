## Context

Settings persist as flat keys in `data/settings.json` (`startingBalance`,
`maxBetPercent`, `paper_mode`, …) while `GET /config` historically returned
the bankroll block from hardcoded `BANKROLL` constants — a read path and a
write path that never met. The HUD keeps two money concepts (paper vs real
ledgers, one active) but displayed a single unlabeled number in two places.
`betHistory` hydration is view-gated in the data-bridge slow poll.

## Goals / Non-Goals

**Goals:**
- Save→reload identity for every settings section.
- Ledger identity always visible; no silent mode flips.
- Every history-consuming view self-sufficient.

**Non-Goals:**
- Wiring saved percentages into the governor (explicit follow-up; staking
  behavior change with its own tests).
- Multi-user settings or per-device profiles.

## Decisions

- **Overlay at read, not migration at write**: the saved file format stays
  flat (back-compatible); `GET /config` merges saved keys over constants.
  Zero migration, zero client changes.
- **Change-guarded resets**: balance resets key off value inequality, so the
  always-sent `startingBalance` field is idempotent for unrelated saves.
- **Badge + split line over rename**: "Capital" stays (operator habit); the
  PAPER/LIVE badge and the untouched-ledger line carry the meaning without
  relabeling treasury concepts mid-flight.
- **Poll preservation over store shape change**: keep the constructed
  bankroll object (with its legacy fallbacks) and add the three missing
  fields — minimal diff, no consumer breakage.
- **Retry in component, not in fetch wrapper**: `apiFetch` stays generic
  (dedup + 429 retry); the settings form owns its cold-start resilience.

## Risks / Trade-offs

- Saved-but-display-only percentages (5/20/5) can mislead operators into
  thinking the governor obeys them — mitigated by documenting the truth
  table; enforcement wiring is the follow-up.
- Paper reset on base change wipes sim P&L by design; acceptable for play
  money, and now at least explicit rather than incidental.
