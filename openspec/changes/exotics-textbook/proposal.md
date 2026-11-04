# Proposal: Exotics Textbook + Track Deep-Dives (OKF)

## Why
Three straight days of exotics dying by one uncovered leg (Oct-2026), and
track knowledge files too thin to steer draw/going decisions (17–69 lines).
TAB form stays the data source of truth; OKF becomes the doctrine layer.

## What changes
- 3 new OKF strategy files (pools reference, construction doctrine,
  Friday-night Phutulicious case study) + punter-rules enrichment of all 7
  live track files. Flamingo Park researched and EXCLUDED (closed Jul-2020).
- Builder: `leg_uncertainty`, `widen_murkiest_legs(budget)`,
  `apply_flagged_horses`, `race_suitability` gate. Existing blueprint output
  unchanged unless callers opt into the new functions.
- Bundle rebuilt: 12 → 15 entries. No deploy until tests green (user order).
