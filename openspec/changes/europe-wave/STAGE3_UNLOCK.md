# Stage 3: Real-Money UK Wagering — Unlock Criteria

Status: LOCKED. Each gate must be demonstrably green before the next opens.
No gate is skipped on confidence; all require measured evidence.

## Gate 1 — Settlement covers UK/IRE (prerequisite: everything else waits)

- `result_tracker` resolves UK/IRE results (ATR results pages carry full
  courses already; extend winner/dividend parsing to UK meetings).
- Proof: 14 consecutive days with zero unsettled UK tickets older than 48h.
- Why first: unstaked winners that never settle corrupt P&L and learnings.

## Gate 2 — Paper-mode Europe staking

- Europe flags stake virtual Rands through the governor's paper path
  (`is_paper=True`, separate paper bank already exists).
- Run 30 days minimum. Metrics reviewed weekly: paper ROI, win rate, edge
  calibration (predicted edge vs realized).
- Advance threshold (proposed): paper ROI > 0% with edge calibration within
  ±3 points over 100+ settled paper bets. Tune with user, don't hardcode blind.

## Gate 3 — Learnings cover UK/IRE

- ROI-by-track/jockey models ingest UK/IRE settled history (same engine,
  region-tagged segments — SA models untouched).
- Proof: UK flag quality improves or holds steady with learnings ON vs OFF
  over the paper window (A/B by week).

## Gate 4 — Real money, capped

- Separate international loss cap (proposed: 10% of bankroll, independent of
  the SA daily limit) + per-bet max lower than SA until 60 days clean.
- Kill-switch: 3 consecutive losing Europe days suspends auto-staking,
  digest-only resumes, user re-enables manually.
- First real-money week: user confirms each ticket manually (supervised),
  then unattended.

## Gate 5 — Full parity review

- 60 days clean → raise caps to SA levels or keep separate by performance.
  Documented in the change log, never silent.
