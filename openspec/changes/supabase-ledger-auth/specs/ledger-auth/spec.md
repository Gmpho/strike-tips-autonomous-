# Capability: supabase-ledger-auth

## Purpose

Ledger and identity live in Postgres with per-user isolation, imported
without loss, while the running system keeps serving from JSON until the
flagged cutover.

## ADDED Requirements

### Requirement: Lossless import with reconciliation gate

The import SHALL refuse to finish unless row counts and money totals match
the JSON source of truth.

#### Scenario: Balanced import
- **WHEN** the import runs against the volume JSONs
- **THEN** inserted bet rows equal source count AND `SUM(profit)` over
  settled equals the JSON-computed P&L AND latest balance matches, else
  the transaction rolls back and nothing is written

#### Scenario: Idempotent re-run
- **WHEN** the import runs twice
- **THEN** the second run inserts zero new rows (`unique(user_id, ref)`
  upsert) and still passes reconciliation

### Requirement: RLS isolates users

No authenticated user SHALL read or write another user's ledger rows
through the Data API roles.

#### Scenario: Cross-user probe
- **WHEN** user A's JWT queries `bets`
- **THEN** zero rows of user B are visible, and writes with another
  `user_id` are rejected by `WITH CHECK`

### Requirement: Fresh start never deletes

"Start fresh" SHALL create a new epoch without deleting history.

#### Scenario: Fresh epoch
- **WHEN** a user selects Start fresh in settings
- **THEN** a new opening snapshot row is written, old bets remain stored
  and queryable, and live P&L computes from the epoch forward
