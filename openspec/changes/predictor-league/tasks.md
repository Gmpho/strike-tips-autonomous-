## 1. Spec lock-in

- [ ] 1.1 Reconcile the WhatsApp poll result into scoring weights/board columns and verify the spec delta still matches the settled design
- [ ] 1.2 Lock the SP feed for the bonus leg (Betway vs ATR) by completeness check and verify the choice is recorded in design.md
- [ ] 1.3 Lock the weekly window definition (presumed Mon–Sun SAST) and verify specs/predictor-league/spec.md states it

## 2. Database migration

- [ ] 2.1 Create Supabase migration for player_profiles, meetings, races, picks, pick_settlements and verify it applies cleanly on a branch
- [ ] 2.2 Add RLS policies (owner-write picks/profiles, public-read aggregates) and verify an anonymous read of another player's private fields is denied
- [ ] 2.3 Add DB-enforced lock (reject pick insert/update inside 5 min of off) plus unique player+race and one-link-per-player constraints, and verify a late insert is rejected with a dry-run matrix

## 3. Scoring engine and backtest gate

- [ ] 3.1 Implement pure score_pick(field_size, position, taken_odds, winner_sp) returning position points, SP bonus, value index, and verify unit tests cover winner/loser/short-vs-long-odds cases
- [ ] 3.2 Implement 30-day form-rating normalization (avg points per settled tip to 0–100) and verify unit tests cover the 5-tip minimum and empty-history edge
- [ ] 3.3 Replay the formula over the settled ledger rows and verify the resulting board ranks skill above favorite-picking (launch gate: must pass before HUD ships)

## 4. Modal API and lock cron

- [ ] 4.1 Add predictor routes (submit pick, board read, profile read, formula data) reusing Telegram identity and verify keyless-safe reads mirror SAFE_PATHS
- [ ] 4.2 Add the lock-enforcer scheduled job flipping race status past the off and verify a locked race rejects picks end to end
- [ ] 4.3 Add hermetic unit tests for lock, duplicate-pick, and duplicate-link rejection and verify pytest passes

## 5. Settlement hook

- [ ] 5.1 Add the predictor_settlement module converting confirmed winners to pick_settlements rows (scheduler-invoked, zero edits to protected settlement files) and verify a settled race produces exact-spec points
- [ ] 5.2 Verify settling league points leaves every ledger balance unchanged and unconfirmed races leave picks pending

## 6. HUD

- [ ] 6.1 Build /predictor (SA cards, per-race pick buttons, countdowns, lock states) and verify npm run build passes
- [ ] 6.2 Build /leaderboard (sortable form/value/strike/weekly/total, SA-default region filter, 5-tip minimum and 7-day decay honored) and verify against seeded data
- [ ] 6.3 Build /tipster/[handle] (hero stats, badges, distribution, form, previous winners, aggregates only) and verify no private fields render
- [ ] 6.4 Publish the scoring formula page with worked examples and verify its math matches the engine output exactly

## 7. Verification and launch

- [ ] 7.1 Run the full Docker suite and verify green before merge
- [ ] 7.2 Launch on SA cards with routes enabled and verify picks, locks, settlement, and board ordering live
- [ ] 7.3 Confirm rollback path (disable routes + HUD nav, no state to unwind) and verify it is documented in the change
