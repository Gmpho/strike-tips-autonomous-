## Context

See proposal.md (Why) and specs/predictor-league/spec.md (behavior contract).
Current state shaping the approach: Supabase project `strike-tips` exists
with a ledger-mirror package in flight (`core_agent/db/`); Modal FastAPI
backend owns routes, the nightly settlement sweep (`result_tracker`), and the
Telegram ST-code/PIN identity; the HUD is Vite + React with `middleware.ts`
origin routing and a `SAFE_PATHS` mirror. The bankroll governor and
settlement core are protected files — this change consumes their outputs and
does not edit them.

## Goals / Non-Goals

**Goals:**

- SA-only predictor game behind a region field that later regions reuse
  unchanged.
- Picks settle to points through the existing results pipeline; money never
  moves.
- Scoring math is a pure, backtestable function proven against the settled
  ledger before launch.

**Non-Goals:**

- Prizes or paid entry (owner: glory only); slip wall; crews; Google login;
  multi-region ingestion. Each is a later change, not scope creep here.

## Decisions

**Storage: new Supabase tables, RLS-enforced.**
`player_profiles` (one row per Telegram link, unique), `meetings`, `races`
(region, off_time, field_size, status, winner, sp), `picks` (unique
player+race, created_at; edits blocked by policy after lock), and
`pick_settlements` (pick → points). RLS: owner-write on picks/profiles,
public-read on board/profile aggregates. Rationale: the repo already
standardized on Supabase for auth-adjacent data and RLS gives us the
published fairness story (lock + caps enforced in the database, not just
the API). Alternative (Modal volume JSONL like the bankroll) rejected: the
board needs concurrent writes from many players and queryable ranking.

**Lock: DB policy + enforcer cron.**
Inserts/updates to `picks` are rejected when the parent race is inside 5
minutes of off (policy reading `races.off_time`), plus a small lock-enforcer
scheduled job flips race status as offs pass. Rationale: defense in depth —
even a buggy API cannot accept a late pick.

**API home: Modal FastAPI.**
New `routes/predictor.py` (picks submit, board read, profile read, formula
page data). Rationale: picks need the service-role DB key and the Telegram
identity check, both of which live server-side; edge stays read-cache duty
and can front the board later without changing the contract.

**Settlement hook: new module, zero protected-file edits.**
A new `predictor_settlement` module runs after the nightly sweep (invoked
from the scheduler, not from inside `result_tracker.py`) and converts
confirmed winners into `pick_settlements` rows. The governor is never
called; points and money cannot intersect by construction. Any future edit
to protected settlement files needs its own approval.

**Scoring: pure function + ledger backtest gate.**
`score_pick(field_size, position, taken_odds, winner_sp)` returns
(position points, sp bonus, value index); form rating normalizes 30-day
average points per settled tip to 0–100. Launch gate: replay the formula
over the 1,600+ settled ledger rows and confirm the board ranks
positive-ROI-style play above favorite-picking — the proof our rivals
cannot show.

**HUD: three pages, shared board kit.**
`/predictor` (today's SA cards, per-race pick buttons, countdowns, lock
states), `/leaderboard` (sortable columns, region filter defaulting to SA),
`/tipster/[handle]` (hero stats, badges, distribution, form, previous
winners). New keyless-safe reads mirror into `SAFE_PATHS`.

**Identity: Telegram link only.**
Registration binds one Telegram link per player (unique constraint); the
existing ST-code/PIN flow is the gate. Google login stays a later change.

## Risks / Trade-offs

- [Off-time drift] → Mitigation: source off times from the same feed the
  offtime-threading work uses; lock uses max(known off, scheduled off).
- [SP source gaps] → Mitigation: SP bonus falls back to field-size points
  only when no SP is confirmed; the fallback is part of the published
  formula, not a silent exception.
- [Multi-account farming] → Mitigation: one Telegram link per player, 5-tip
  minimum, 7-day decay; farming earns badges on dead accounts nobody sees.
- [Poll moves the goalposts] → Mitigation: explicit reconcile-with-poll task
  before apply completes (roadmap sequencing).
- [Board query cost at scale] → Mitigation: precomputed weekly/total columns
  updated by the settlement hook; no live aggregation over full history.

## Migration Plan

1. Supabase migration (tables + RLS + constraints) on a branch; verify with
   a dry-run insert/reject matrix.
2. Modal routes + lock enforcer behind disabled-by-default wiring; no traffic
   until HUD ships.
3. Settlement-hook module + ledger-backtest gate (must pass before launch).
4. HUD pages; keyless-safe reads; `npm run build`.
5. Docker-green suite + launch on SA cards; rollback = disable routes and
   HUD nav (no money or ledger state involved, nothing to unwind).

## Open Questions

- WhatsApp poll result: folds into scoring weights or board columns via the
  reconcile task; cannot change the lock/settlement contract, only tuning.
- Exact SP feed for the bonus leg (Betway vs ATR): decided at apply time
  from whichever feed proves more complete during backtest.
- Weekly window definition (Mon–Sun SAST presumed): locked during apply.
