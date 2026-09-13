## Purpose

Professional, banking-grade performance analytics that load fast and never lie about denominators.

## ADDED Requirements

### Requirement: Lazy treeshaken chart suite

Analytics charts SHALL load in an on-demand chunk (core + used types only) so dashboard first paint never pays for them; a native wrapper SHALL be used instead of react-apexcharts.

#### Scenario: Dashboard first paint
- **WHEN** the dashboard loads without visiting Analytics
- **THEN** no apexcharts bytes are fetched

### Requirement: Settled-only KPIs

Win rate and average stake SHALL be computed over settled bets (wins + losses) only, consistent with the win/loss donut.

#### Scenario: Large open backlog
- **WHEN** 1000 PENDING rows exist alongside 200 settled
- **THEN** win rate reflects the 200 settled, not all 1200
