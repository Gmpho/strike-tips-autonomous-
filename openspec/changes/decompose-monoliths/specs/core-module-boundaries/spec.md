## Purpose

Keeps the live racing card, picks and settlement inputs byte-for-byte stable
while oversized backend modules are split into smaller units, so downstream
callers never have to change because of an internal reorganisation.

## ADDED Requirements

### Requirement: Stable import contract for downstream callers

Symbols importable from an existing backend module before decomposition MUST
remain importable from that same module after decomposition, with unchanged
signature, argument order and return shape. Moving an implementation into a
new module MUST keep a re-export at the original location.

#### Scenario: Existing downstream import still resolves

- **WHEN** a backend module that previously exposed a helper is split and the helper's implementation moves to a new module
- **THEN** importing that helper from the original module succeeds with the same name and callable signature
- **AND** every production and test caller continues to work without edit

#### Scenario: Return shape is unchanged

- **WHEN** a moved helper is called with the same inputs as before the split
- **THEN** it returns the same keys, types and value semantics as the original implementation

### Requirement: Unchanged published snapshot for identical inputs

Decomposition MUST NOT change the market snapshot observed by the HUD, picks,
Telegram or Cloudflare bridge: event identifiers, event counts, runner order,
price semantics, timestamps and status flags MUST be identical for the same
inputs.

#### Scenario: Before/after snapshot comparison

- **WHEN** the same recorded cycle inputs are processed before and after a decomposition phase
- **THEN** the resulting published snapshot is equivalent field for field
- **AND** no race gains or loses a real price, form field, off-time or status flag

#### Scenario: No net-negative coverage

- **WHEN** a decomposition phase completes
- **THEN** no existing test is deleted, skipped or weakened
- **AND** the Docker test suite passes in full before any deployment

### Requirement: Single lifecycle owner

Exactly one component MUST own startup, periodic cycle execution, shutdown and
background task registration for the odds monitor. Extracted helper components
MUST NOT register schedulers, start loops, write the published snapshot or
spawn background tasks on import.

#### Scenario: One cycle produces one set of side effects

- **WHEN** the odds monitor executes one complete cycle after decomposition
- **THEN** exactly one cycle run is recorded
- **AND** telemetry, digests and market events are emitted once per cycle, not duplicated per helper

#### Scenario: Helper import is inert

- **WHEN** an extracted helper module is imported without the orchestrator
- **THEN** no network request, volume write, cron registration or background task occurs

### Requirement: Characterisation before movement

Behaviour relied on by existing tests MUST be captured by a passing test before
the code is moved, and MUST still pass after the move.

#### Scenario: Protected tests remain green

- **WHEN** a helper used by an existing test is moved to another module
- **THEN** that test passes unchanged against the re-exporting module
- **AND** the Docker suite reports no new failure attributable to the move
