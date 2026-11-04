## Why

The November roadmap commits to a predictor-first community: a free race-day
game (one pick per race, locked before the off, points for winners, public
leaderboard) that turns the Telegram/WhatsApp community into daily-active
players on our own surface. SA race cards are the launch wedge and other
regions plug in later in November, so the design carries a region field from
day one instead of hardcoding SA.

## What Changes

- **Predictor game (SA launch):** one pick per race per player on SA cards
  (Turffontein, Vaal, Greyville, Fairview, Durbanville, Kenilworth); hard lock
  5 minutes before the off, DB-enforced, no edits after lock.
- **Published scoring:** position points scaled by field size + winner's
  starting-price bonus + a transparent value index weighted by odds beaten.
  The full formula with worked examples ships on the page itself.
- **Leaderboard:** sortable by rank, player, form rating (0–100, last 30 days),
  value index, strike rate, weekly points, and total points. Minimum 5 settled
  tips to rank; accounts with no 7-day activity decay off the board.
- **Player profiles:** hero stats, achievement badges (win milestones, streaks,
  exact forecasts, meeting sweeps), finish-position distribution, recent form,
  favorite tracks, previous-winners table. Aggregates only — no endpoint
  returns another player's private data.
- **Fairness rules (published):** one account per human via Telegram link,
  lock times, anti-farming minimums. No prizes in this change — glory only,
  per owner decision; retention rides on badges, streaks, and crews (later).
- **Settlement reuse:** picks settle to points (never money) through a hook
  into the existing nightly settlement sweep. The bankroll governor is
  untouched; any edit to protected settlement files needs separate approval.
- **Region-ready schema:** every meeting/race carries a region so additional
  regions activate later in November without migration.

## Capabilities

### New Capabilities

- `predictor-league`: race-day predictor game — picks, locks, scoring,
  leaderboard, player profiles, fairness rules, and settlement hook.

### Modified Capabilities

- None. Existing settlement, ledger, and auth requirements are reused
  unchanged; the predictor consumes race results and the Telegram identity
  without altering their behavior.

## Impact

- **Supabase:** new migration — `player_profiles`, `meetings`, `races`,
  `picks`, `pick_settlements`, `player_reports`; RLS owner-write/public-read;
  DB-enforced photo/pick caps where applicable.
- **Modal backend:** new routes for picks, leaderboard, and profiles; a lock
  enforcer cron; a new settlement-hook module called from the sweep
  scheduler (protected files only change under separate approval).
- **HUD:** three new pages (`/predictor`, `/leaderboard`, `/tipster/[handle]`)
  plus shared board components; keyless-safe routes mirror `SAFE_PATHS`.
- **Auth:** reuses the existing Telegram ST-code/PIN identity; no Google
  login in this change.
- **Roadmap:** carries a "reconcile with WhatsApp poll" task — the poll is
  still open and its result folds into the spec before apply completes.
