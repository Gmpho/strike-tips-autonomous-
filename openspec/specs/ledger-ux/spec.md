# ledger-ux Specification

## Purpose
A trustworthy executions ledger: every row timestamped, statused, and grouped like a banking app.

## Requirements

### Requirement: Timestamped grouped ledger

Executions SHALL render newest-first with SAST date + time on every row, grouped under day headers (Today, Yesterday, dates), with WON/LOST/OPEN/VOID/EXPIRED pills and per-row P&L for settled bets.

#### Scenario: Oldest rows exist
- **WHEN** history holds rows back to July
- **THEN** the ledger still opens on today's rows with correct dates, never the oldest 20

### Requirement: Ledger filters and paging

The ledger SHALL offer All/Wins/Losses/Open filters and paginate (30 + show-more) instead of truncating.

#### Scenario: Filtering wins
- **WHEN** the user taps Wins
- **THEN** only WON rows show, still newest-first with timestamps
