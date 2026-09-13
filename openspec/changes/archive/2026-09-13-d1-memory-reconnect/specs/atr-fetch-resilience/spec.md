## ADDED Requirements

### Requirement: KV snapshot write budget

Snapshot pushes to KV SHALL cost at most one write per push (single full-snapshot put, skipped entirely when content is unchanged). Per-event fan-out is forbidden: ~130 puts per push exhausts the 1k/day free quota within the first hour.

#### Scenario: Unchanged overnight snapshot
- **WHEN** the monitor pushes an identical snapshot
- **THEN** the worker answers `unchanged` with zero writes
