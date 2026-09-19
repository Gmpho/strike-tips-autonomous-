# settlement-voids Specification (delta — extends settlement-accounting)

## Purpose

Close the two ways a ticket could take money without a fair result:
scratched horses scored WON/LOST, and abandoned meetings stranding stakes
in PENDING until a no-refund EXPIRED.

## ADDED Requirements

### Requirement: Non-runner auto-void

The system SHALL mark a single VOID with full stake refund (never WON/LOST)
when the horse is flagged scratched in the merged snapshot (`non_runner`
or `odds == "NR"` from Betfair REMOVED / Betway nonRunner).

#### Scenario: Scratched single is voided with refund

- **WHEN** a PENDING single's horse is in `_snapshot_non_runners` for its
  (course, race, date)
- **THEN** settlement SHALL `cancel_pending_bet` with a scratched note,
  exclude the record from D1 learning, and skip Telegram result noise.

### Requirement: Abandoned-meeting void (singles)

The system SHALL VOID all PENDING singles of a meeting with refund when the
board is fully dark: every open single past off-time + 90 minutes, the ATR
day fetch succeeds overall, and zero results exist for the track.

#### Scenario: Dark board voids pending singles

- **WHEN** `_meeting_is_abandoned` returns true for a (track, day)
- **THEN** each PENDING single SHALL be voided with "Meeting abandoned —
  stake refunded", mirrored to the ledger, excluded from D1, and followed by
  one Telegram summary per meeting.

#### Scenario: Slow feed is not read as abandoned

- **WHEN** any open single is not yet past grace, or the track has any
  results, or the ATR day fetch failed
- **THEN** the system SHALL NOT declare abandonment (a slow feed must never
  read as a dark board).

### Requirement: Exotic build guards

The system SHALL drop an exotic play before carding when (a) fewer than half
its bankers run today (phantom meeting), (b) fewer than half its judged legs
anchor at 6.0 or shorter (all-outsider ticket), or (c) any candidate is a
non-runner. Legs with unknown odds SHALL NOT count against the play.

#### Scenario: Weak exotic ticket is dropped before carding

- **WHEN** fewer than half the bankers run today, or fewer than half the
  judged legs anchor at 6.0 or shorter, or any candidate is a non-runner
- **THEN** the play SHALL be dropped before carding, and legs with unknown
  odds SHALL NOT count against the play.
