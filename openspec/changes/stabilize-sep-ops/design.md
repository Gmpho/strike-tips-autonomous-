# Design — stabilize-sep-ops

## Principles

1. **Drop only on proof.** Phantom, balance, NR, and abandonment guards all
   pass when data is missing and kill only on positive evidence. Unknown
   stays unknown; nothing settles, voids, or refuses on a failed fetch.
2. **Money moves once, visibly.** VOID refunds from the originating ledger,
   excluded from learning/ROI mirrors, notified once (`mark_notified`).
   EXPIRED moves nothing.
3. **Web serves; crons work.** Request containers carry no loops, no
   schedulers-of-record beyond settlement jobs, no LLM warmups. Scraping,
   swarm, news, and heartbeat live in cron cadence (piggybacked where the
   5-cron cap forces it).
4. **Budgets are structural, not hoping.** TPM ceiling enforced by prompt
   shape (tested), not retries; ticket counts by form state; container
   count at one keeper.
5. **Local dev spends nothing.** Backend defaults to docker; prod is an
   explicit, badged opt-in.

## Key decisions

- Abandonment grace 90 min + ATR-day-OK + track-empty triple gate; singles
  only (exotic tote rules need domain input first).
- Chat refusal lives in `_try_snapshot_answer` AFTER data branches, so real
  movers/predictor/results/track answers always win; pasted cards bypass via
  odds/form pattern detection.
- Honcho sanitization at the boundary (`_safe_honcho_id`); JSONL keeps raw keys.
- Model IDs are data verified against live provider lists, not docs or
  memory — `test_cloud_routing.py` fails the build on any dead ID.
