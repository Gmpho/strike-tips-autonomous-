## 1. Betfair parser emits exact offTime

- [x] 1.1 Add `_off_time_from_market` to prefer `marketStartTime` (top-level epoch) and `_event_date_from_market` from event name, with `+60d` year roll; verify `offTime` and `eventDate` on a real Fairview payload
- [x] 1.2 Add `_clean_course` decoration strip and `_distance_from_market` (`1200m`/`6f`/`1m1f`) with `>=100` magnitude rule; verify 1200, 1207, 1811
- [x] 1.3 `get_form_format` stores `market_info` with course/timeLabel and overrides market payload on assembly; verify `TOMORROW` 169 events

## 2. Merge stamps bf_off_time + course/raceNumber fallback

- [x] 2.1 `_merge_bf_into` fallback match on `(course, raceNumber)` when `t` mismatches; verify `state` gains `bf_off_time` even with `12:00` vs `14:05`
- [x] 2.2 Stamp `bf_off_time`, `bf_event_date`, `distance_m` additively; verify snapshot `bf_off_time` present and `t` untouched

## 3. Tracker prefers bf_off_time

- [x] 3.1 `_find_race_time` prefers snapshot `bf_off_time` when `bf_event_date` matches bet date, else scan file; verify
- [x] 3.2 `_race_off_datetime` returns SAST-aware datetimes and respects `bf_event_date` mismatch; verify `tzinfo is not None`
- [x] 3.3 Gate compares `datetime.now(_SAST)` with `+OFF_TIME_GRACE_MINUTES`; verify pre-race stays PENDING

## 4. Tests + deploy + live verify

- [x] 4.1 145 tests green, Modal deployed, live snapshot `Churchill R11 18:45` match
