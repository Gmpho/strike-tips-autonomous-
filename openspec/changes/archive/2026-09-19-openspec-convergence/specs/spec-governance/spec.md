## Purpose

Keeps the OpenSpec store trustworthy as the project's declared source of truth: change deltas stay parseable and validatable, one subject maps to one capability, cloud model identifiers have a single authoritative definition, documented platform facts match the platform actually serving traffic, and documented metrics can be reproduced from repository tooling.

## ADDED Requirements

### Requirement: Change deltas SHALL pass openspec validate

Every change under `openspec/changes/` SHALL contain at least one spec delta that the OpenSpec parser recognises. Delta files SHALL place operation headers (`ADDED`, `MODIFIED`, `REMOVED`, `RENAMED` Requirements) at heading level 2, SHALL name each requirement with an `### Requirement:` heading, and SHALL give every requirement at least one `#### Scenario:` block written in WHEN/THEN form. A change that intentionally modifies no spec behaviour SHALL declare `skip_specs: true` in its `.openspec.yaml` rather than invent a requirement to satisfy validation.

#### Scenario: Delta using the correct heading levels validates

- **WHEN** `openspec validate <change>` runs against a change whose delta uses `## ADDED Requirements`, `### Requirement:` and `#### Scenario:` headings
- **THEN** the command reports no errors and the change reports at least one parsed delta

#### Scenario: Operation header at heading level 3 is rejected

- **WHEN** a delta opens its operation section with `### ADDED Requirements` instead of `## ADDED Requirements`
- **THEN** `openspec validate` fails with "No delta sections found" and the change's delta count is zero

#### Scenario: Requirement without a scenario is rejected

- **WHEN** a delta declares a requirement containing `SHALL` behaviour but no `#### Scenario:` block
- **THEN** `openspec validate` fails and names the offending requirement

### Requirement: One subject SHALL map to exactly one capability

The spec store SHALL NOT contain two capabilities describing the same subject. Where a subject already has a capability, a later change SHALL extend it through `## MODIFIED Requirements` instead of introducing a parallel capability name.

#### Scenario: Parallel capability names for one subject are consolidated

- **WHEN** two changes declare capabilities covering the same subject, such as `cloud-models` and `cloud-models-correction`
- **THEN** the duplicate is merged into the pre-existing capability and the redundant capability name is removed

#### Scenario: Extending an existing capability preserves its identity

- **WHEN** a change alters behaviour belonging to an existing capability
- **THEN** the delta uses the existing capability path and declares `## MODIFIED Requirements` rather than creating a second capability for that subject

### Requirement: Cloud model identifiers SHALL have a single source of truth

The set of permitted cloud model identifiers SHALL be defined in exactly one authoritative capability spec. Every other reference — provider routing code, cloud-model documentation, and any model warm-up script — SHALL agree with that spec, and a reference naming a model absent from the spec SHALL be treated as a defect rather than tolerated drift.

#### Scenario: Reference disagrees with the authoritative spec

- **WHEN** a model identifier appears in provider routing code, documentation, or a warm-up script but is absent from the authoritative capability spec
- **THEN** the discrepancy is reported as a defect and the reference is reconciled to match the spec

#### Scenario: Retired model remains referenced

- **WHEN** documentation records that a model has been retired by its provider while another file still routes to that model
- **THEN** the stale reference is removed so no request can fail into paid fallback spend

### Requirement: Documented platform facts SHALL match the deployed platform

Documentation SHALL name only the hosting platform that actually serves traffic. Deployment instructions, badges, and architecture descriptions belonging to a decommissioned platform SHALL be removed rather than retained as a dormant fallback, and platform-specific configuration or middleware files belonging to that platform SHALL be deleted from version control.

#### Scenario: Decommissioned platform appears in documentation

- **WHEN** the frontend is served exclusively by Cloudflare Pages
- **THEN** no tracked documentation instructs a reader to deploy to, or describes request routing performed by, a decommissioned platform

#### Scenario: Dead platform artifacts are removed

- **WHEN** the frontend no longer deploys to a platform whose middleware or configuration files remain in the repository
- **THEN** those files are deleted from version control

#### Scenario: A single deployment document is authoritative

- **WHEN** a reader needs deployment steps for the frontend, the edge worker, or the backend
- **THEN** exactly one tracked document contains those steps and it names the platform currently serving each layer

### Requirement: Documented metrics SHALL be reproducible

Quantitative and stateful claims in documentation — test counts, canonical spec inventories, and active-change state — SHALL match the values produced by the repository's own tooling, and SHALL be corrected whenever the tooling disagrees.

#### Scenario: Documented test count differs from the suite

- **WHEN** documentation states a test count that differs from the count reported by the project's test collection command
- **THEN** the documented count is corrected to the reproducible value

#### Scenario: Active-change state has drifted

- **WHEN** documentation states that no change folders are active while `openspec list` reports active changes
- **THEN** the documented state is corrected to match the tooling output

#### Scenario: Canonical spec inventory is stale

- **WHEN** documentation lists the canonical capabilities and omits capabilities present in `openspec/specs/`
- **THEN** the documented inventory is corrected to match the store