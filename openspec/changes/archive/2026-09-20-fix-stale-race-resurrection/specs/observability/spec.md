# observability — ADDED Requirements

## ADDED Requirements

### Requirement: Snapshot freshness is queryable

`/api/monitoring/snapshot` and `/api/monitoring/snapshot-hash` SHALL include
`snapshot_age_secs` and `snapshot_source` derived from the in-memory snapshot
metadata, so a client can badge a stalled feed instead of rendering stale races
as live.

#### Scenario: Monitor cron is late

- **WHEN** the last snapshot write was 12 minutes ago
- **THEN** `snapshot_age_secs` is ~720 and `snapshot_source` names the last writer (monitor, disk poll, or scan)

### Requirement: Monitor cycles emit liveness signals

Every shipped odds-monitor cycle (`run()` loop and `run_single_cycle()` cron)
SHALL append a `SYNC_COMPLETE` healing event with the pruned race count and
SHALL emit one telemetry event for the cycle, so the Live-Ops and Telemetry
pages show 5-minute liveness instead of only failure events.

#### Scenario: Quiet but healthy afternoon

- **WHEN** the 5-minute cron completes with 58 live races and no failures
- **THEN** `/api/healing/activity` shows a `SYNC_COMPLETE` event for that cycle and `/api/telemetry` carries an odds-cycle entry

### Requirement: Vitals expose the monitor container

`/api/system/vitals` SHALL include a synthetic monitor row reporting the live
race count, the snapshot age and its source, because the odds monitor runs in a
separate cron container whose health is otherwise invisible to the web
container.

#### Scenario: Vitals page inspection

- **WHEN** an operator opens the Vitals page
- **THEN** alongside the orchestrator row there is an "ODDS MONITOR (5-MIN CRON)" row marked LIVE or STALE with the snapshot age in minutes
