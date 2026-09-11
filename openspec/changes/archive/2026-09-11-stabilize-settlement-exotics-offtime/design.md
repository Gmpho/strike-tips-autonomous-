## Context

Betfair markets carry the only authoritative clock (`marketStartTime` epoch) and meeting date (`"Fairview (RSA) 11 Sep"`); TAB/Betway times are placeholders (`12:00`) that broke settlement and merging. Exotics were single-day and numeric-cloth bugs produced `#1` bankers. Volume mounts in long-lived Modal containers freeze without explicit `reload()`.

## Goals / Non-Goals

**Goals:** exact SAST off-times and dates threaded to settlement and display; SAST-aware gate; numeric-name rejection; multi-day exotic board; distance display; volume freshness.

**Non-Goals:** changing market discovery (Betway/TAB) or staking math.

## Decisions

* Course cleaning + `eventDate` parsing + `marketStartTime` → `offTime` as first-class event fields, never fabricated.
* Fallback merge on `(course, raceNumber)` when `t` disagrees; additive `bf_off_time`/`bf_event_date`/`distance_m`.
* Gate prefers `bf_off_time` only when `bf_event_date` matches the bet date; else scan time; SAST-aware datetimes.
* Exotic history merge-by-day + prune-past; numeric guard at scraper and builder; distance `m`/`f`/`m+f` parser.
* `volume_sync.py` throttled reload in middleware/SSE/scheduler.

## Risks / Trade-offs

* Betfair date parsing assumes English month abbreviations; fallback to scan time if parse fails.
* Distance `m` alone ambiguous (`1200m` vs `1m`); `>=100` rule.
* Volume reload throttling could briefly delay visibility; 30s guard is a balance.
