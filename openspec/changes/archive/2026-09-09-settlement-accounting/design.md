## Context

Settlement runs inside `check_race_results_job` (APScheduler, every 5 min,
`core_agent/core/scheduler.py`) and inside Modal/Telegram flows via
`ResultTracker.check_and_settle_open_bets()`. The bankroll governor
(`core_agent/skills/bankroll_manager/governor.py`) owns money movement with
atomic file transactions; single bets hold exposure at placement and apply
P&L at settle, exotics deduct ticket cost at placement and credit dividends
at settle. All analytics read settled bets only, so a dead settler empties
every downstream surface.

## Goals / Non-Goals

**Goals:**
- Every resolvable recent bet settles win AND loss automatically.
- Stale backlog can neither mis-settle nor block new betting.
- Reports cover any date; mornings recap yesterday automatically.
- History chart always ends at the live balance, never negative.

**Non-Goals:**
- Exotic dividend settlement (needs pool dividend data — tickets stay PENDING
  by design, skipped cheaply).
- Changing staking math (Kelly/DSI/caps untouched).
- Wiring settings percentages into the governor (display-only, separate change).

## Decisions

- **ATR labels over URL surgery**: map ISO→relative at the tracker boundary
  (`atr_date_label()`), keeping the ATR parser's relative-URL contract intact.
- **Fail-open dates, fail-closed ages**: unparseable dates still settle (rare,
  DDGS handles them); over-age bets never settle (wrong-race risk).
- **Settled-flag over exceptions**: `strike.settle_bet` returns status dicts
  by contract, so success is read from the payload, not inferred.
- **Backward balance reconstruction**: forward reconstruction can't end at the
  live balance once refills exist; backward walk guarantees it, flooring at 0.
- **Exposure default excludes stale**: limits and display share the active
  figure; gross remains available via `include_stale=True`.
- **Shared `MAX_SETTLE_AGE_DAYS`** between tracker and governor (single policy
  knob, governor imports it lazily to avoid cycles).

## Risks / Trade-offs

- Old bets mapped to `yesterday` can still theoretically hit the wrong race —
  contained by the 3-day deferral.
- Paper refills remain unledgered; history shape under heavy refill drift is
  approximate (end-exact, start-floored).
- Morning recap depends on the 5-min settler having run overnight; a total
  results outage yields a pending-heavy recap (truthful, not wrong).
