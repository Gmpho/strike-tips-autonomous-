# cloudflare-hud-hosting — ADDED Requirements

## ADDED Requirements

### Requirement: Edge odds cache survives a missed cycle

`/api/ingest-snapshot` SHALL store the full snapshot with a KV TTL of at least
three monitor cycles (900 s at the 5-minute cadence), so a single late or
stalled cron cycle cannot blank `/api/racing/odds` for readers.

#### Scenario: Monitor cycle runs late

- **WHEN** the monitor push is 8 minutes late
- **THEN** `/api/racing/odds` still serves the previous snapshot instead of `{"note": "No snapshot available"}`

### Requirement: Edge prunes finished and expired races

The worker SHALL drop `isFinished` races and races whose `expires_at` has
passed, both when ingesting a snapshot and when serving the full snapshot, so a
stale KV entry can never re-serve the morning card.

#### Scenario: Stale KV entry served

- **WHEN** `/api/racing/odds` reads a snapshot whose live races have since finished
- **THEN** the response contains only races whose `expires_at` is still in the future (or that carry no expiry stamp)

#### Scenario: Ingest of an unpruned payload

- **WHEN** a producer pushes a snapshot containing finished races
- **THEN** the stored payload is pruned and the reported `events` count is the post-prune count

### Requirement: HUD enforces race expiry client-side

The HUD DataBridge SHALL drop `isFinished` and expired (`expires_at` in the
past) races at ingestion, and SHALL refresh immediately — resetting any polling
backoff — when the tab becomes visible or regains focus, so a long-lived or
backgrounded tab cannot display finished races or hour-old feeds.

#### Scenario: Tab left open over several races

- **WHEN** a user returns to a dashboard tab that has been idle for 30 minutes
- **THEN** the fresh snapshot is fetched immediately, its finished races are dropped before rendering, and polling backoff is reset to the fast interval
