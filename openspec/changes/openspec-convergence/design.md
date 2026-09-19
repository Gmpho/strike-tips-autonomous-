## Context

The store's authority is asserted in three places (`AGENTS.md`, `docs/openspec-usage.md`, `openspec/project.md`) and enforced nowhere. The concrete constraints discovered while investigating:

- The OpenSpec 1.11.0 validator is strict about heading levels. `### ADDED Requirements` yields `deltaCount: 0` and the message `No delta sections found`; the requirement/scenario pairing rules are printed only after that first failure, which is why the real cause reads as "missing scenarios". Verified by `openspec show refactor-cloud-models --json --deltas-only` returning an empty `deltas` array.
- Four changes are implemented and green in their own terms (`stabilize-sep-ops/tasks.md` records all boxes checked and 245 tests passing in Docker) but cannot be archived, so `openspec/specs/` is four capabilities behind the code.
- The model-ID conflict is not theoretical: `docs/CLOUD_MODELS.md` opens with the incident it caused, and `stabilize-sep-ops/proposal.md` records `refactor-cloud-models`' premise as "inverted".
- The Vercel path is demonstrably dead: the live site serves Pages Functions (`/api/health` → worker, `/api/system/health` → Modal, both HTTP 200), and there is no `functions/_middleware.ts`, so the Vercel-style `middleware.ts` never executed on Pages.
- Documentation metrics are wrong in the direction of understatement: docs say 30 and 44 tests; collection reports 261.

## Goals / Non-Goals

**Goals:**

- Make every active delta validate, then archive the four completed changes so `openspec/specs/` reflects the running system.
- Collapse duplicate capabilities and give cloud model identifiers exactly one authoritative definition.
- Make the documented platform story match the platform actually serving traffic, and reduce deployment instructions to one document.
- Leave a reproducible statement of test count, canonical capabilities, and active changes.
- Make the governance rules themselves checkable from the repo's own tooling.

**Non-Goals:**

- No runtime, API, money-path, or bankroll-governance change. This change must not alter settlement, staking, or tool behaviour.
- Not a re-litigation of the archived changes' technical content — their requirement text is repaired to the required format, not redesigned.
- Not fixing the separately-reported production findings (`restore-hud-write-path`, `harden-pages-functions`); those are their own changes, and this one lands first so they can be written against valid specs.
- Not rewriting history: Vercel mentions inside `openspec/changes/archive/**` are historical records and stay as written. Only live documentation is corrected.

## Decisions

1. **Repair heading levels, don't restructure content.** The failure is presentational: `###` → `##` for operation headers, h4 requirement names → `### Requirement: <name>`, and confirmation that each requirement already carries a `#### Scenario:` block. Alternatives rejected: rewriting the deltas from scratch (destroys reviewer-visible history and risks silently changing accepted behaviour) and deleting the changes unarchived (the capabilities would never reach `specs/`).

2. **Merge `cloud-models-correction` into `cloud-models` before archiving.** Order matters: the duplicate must be folded while both deltas are still change-scoped. Archiving first would create two canonical capabilities that could never be cleanly merged.

3. **One authoritative model list, referenced by name everywhere else.** The list lives in the `cloud-models` capability; `docs/CLOUD_MODELS.md` becomes a pointer plus the live `/models` verification recipe rather than a second list; routing code and the warm-up script are reconciled to it. When the two disagree, a live `/models` probe is the arbiter — the discipline already recorded in `docs/CLOUD_MODELS.md`.

4. **Delete the Vercel path outright rather than gate it.** Retaining it as a "paused fallback" preserves a latent confused-deputy hazard: `middleware.ts` forwards every state-changing write with the master key injected while guarding only `/api/agent/{kill,reset}`, whereas the Pages proxy guards all write families. Since Vercel is no longer deployed to, deletion removes the trap. One-way door acknowledged; git history is the recovery path.

5. **Archive is the completion signal, not the validate result.** A green `openspec validate` proves the delta parses, not that the capability belongs in `specs/`. Archiving happens only after the repaired deltas parse *and* the suite is confirmed green, preserving the repo's "archive only when green" rule.

6. **Governance rules are stated as checkable scenarios.** Each requirement above maps to a command (`openspec validate`, `openspec list`, the test-collection count, a grep for decommissioned-platform references), so the contract is verified mechanically instead of by convention.

## Risks / Trade-offs

- **Archiving looks destructive.** It moves change folders into `changes/archive/` and writes into `openspec/specs/`. Mitigation: validate before each archive, one commit per archived change, and `git revert` as the rollback.
- **Repairing scenario text could change meaning.** Mitigation: only heading levels and requirement-name prefixes are edited; scenario prose is left intact and each repaired delta is diffed before archiving.
- **Model-list reconciliation could pin an ID the provider has since retired.** Mitigation: probe the providers' live `/models` endpoints as the arbiter before writing the authoritative list and record the probe date; treat an unverifiable identifier (the Live API model exposes no list endpoint) as explicitly *unverified* rather than silently authoritative.
- **Deleting the Vercel artifacts removes a rollback path** if Pages ever breaks. Mitigation: `docs/DEPLOY.md` records Modal as the backend of record and Pages as the only frontend; returning to Vercel would be a deliberate re-addition with write-guard parity fixed first, not a config toggle.
- **Doc-truth edits touch a model warm-up string and a provider alias tuple** in code-adjacent files. Mitigation: both edits are behaviour-preserving, constrained by the existing cloud-routing tests, which must stay green before archiving.
- **Scope creep into the production findings.** This change deliberately contains no behavioural fix; the P1 write-path break, the write-guard boundary hole, and the quota-burn findings are separate changes. Mixing them would make this governance cleanup unreviewable.