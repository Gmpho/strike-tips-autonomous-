# Tasks: League race identity by off-time

## 1. Off-time resolution

- [x] 1.1 `_utc_hhmm()` helper: ISO off-time (any offset) → UTC "HH:MM"
- [x] 1.2 Time index alongside the race-number index in `load_winner_details`
      (ATR title times are UTC; confirmed cards use their new `off_time_utc`)
- [x] 1.3 `settle_open_picks` resolves a pick against the off-time race when
      that race contains the picked horse; otherwise the race-number path
- [x] 1.4 `rescore_settled_picks` resolves the same way

## 2. Mis-numbered pick repair

- [x] 2.1 `repair_misnumbered_picks()`: renumber a pick when ATR proves a
      different race for the pick's own off time AND the horse is on it
- [x] 2.2 Keep the original number in `race_number_corrected` (audit trail)
- [x] 2.3 Never touch a pick settled with a finishing position; never
      downgrade a verdict
- [x] 2.4 Run the repair before the re-score in the settle pass

## 3. Card time keys

- [x] 3.1 Raceform cards carry `off_time_utc` (SA wall clock → UTC)
- [x] 3.2 Offtrackbetting cards carry `off_time_utc` (already UTC)
- [x] 3.3 Cards without a resolvable time keep the race-number path

## 4. Tests

- [x] 4.1 A pick with a shifted race number settles against the race ATR
      proves for its off time
- [x] 4.2 The repair pass renumbers the pick and keeps the original value
- [x] 4.3 A horse on neither card stays PENDING (no false loss)
- [x] 4.4 A pick settled with a position is never renumbered
- [x] 4.5 `off_time_utc` written for Raceform and Offtrackbetting cards
- [x] 4.6 Existing league + settlement suites still green

## 5. Ship

- [x] 5.1 Full suite green in docker (host runs lack fastapi), commit, push
- [ ] 5.2 Deploy on the user's approval
