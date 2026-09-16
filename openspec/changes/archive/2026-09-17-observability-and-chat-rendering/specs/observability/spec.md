## Purpose

Make every production incident solvable with one grep: shared ids, queryable logs, honest levels.

## ADDED Requirements

### Requirement: Flow correlation IDs

Scan, settle, and chat flows SHALL bind a prefixed unique id at entry, tag key log lines with it, and append it as a trailing token on Telegram notifications.

#### Scenario: Crossed settle investigated
- **WHEN** a Telegram result looks wrong
- **THEN** its trailing token greps the exact scan/settle log lines

### Requirement: JSON logs on Modal

Containers running under `MODAL_TASK_ID` (or `LOG_FORMAT=json`) SHALL emit one JSON object per record (ts, level, logger, msg); all other environments keep human-readable lines.

#### Scenario: Tail and filter
- **WHEN** tailing Modal logs
- **THEN** each line parses as JSON with the correlation id where bound

### Requirement: Honest log levels

Routine, retried, or degraded-but-handled events SHALL log at info/debug; 429 rate limits and money-path failures SHALL stay warnings with key fields.

#### Scenario: Quiet overnight
- **WHEN** fallbacks fire normally overnight
- **THEN** no warnings appear unless money or limits are involved
