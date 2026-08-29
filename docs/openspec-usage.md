# OpenSpec at Strike Tips — Usage Guide

OpenSpec (v1.11.0) is the **spec-driven source of truth** for this repo. Every
feature or behavior change flows through a *change proposal* whose spec deltas
are reviewed, implemented, and then promoted into the canonical `openspec/specs/`
store. This keeps the 3-layer racing stack (Cloudflare / Modal / Vercel)
documented as enforceable `SHALL` requirements instead of tribal knowledge.

> **Rule #1 — the spec is truth.** Before proposing or implementing anything,
> read `openspec/project.md` (the "Brain"): it describes the architecture,
> constraints, and conventions so agents don't hallucinate structure.

---

## 1. Directory layout

```
openspec/
├── project.md                      # The Brain — always read first
├── config.yaml                     # OpenSpec schema/config
├── specs/                          # CANONICAL, accepted specs (one dir per capability)
│   └── swarm-researcher/spec.md    #   e.g. promoted after archive
└── changes/                       # ACTIVE + archived change proposals
    ├── <kebab-name>/              #   an open change (delta)
    │   ├── proposal.md            #     Why / What Changes / Impact
    │   ├── design.md              #     Context, Goals, Decisions, Risks
    │   ├── tasks.md               #     checkbox task list (apply tracks these)
    │   └── specs/<capability>/spec.md   # ADDED/MODIFIED requirements (the delta)
    └── archive/                   #   closed changes (historical record)
        └── 2026-08-29-add-swarm-researcher/
```

- **`specs/`** = what the system *currently* must do. Committed and version-controlled.
- **`changes/`** = what we're *about to* change. Deleted on archive (moved to `archive/`).

---

## 2. The change lifecycle

```
explore ──▶ propose ──▶ apply ──▶ archive
 (read)      (plan)     (build)   (promote)
```

| Phase | CLI | Slash/skill | Purpose |
|-------|-----|-------------|---------|
| **Explore** | `openspec list` / `openspec view` / `openspec doctor` | `/opsx:explore` | Zero-risk investigation before coding. |
| **Propose** | `openspec change` (or skills) | `/opsx:propose` | Scaffold `proposal.md` + `design.md` + `specs/.../spec.md` + `tasks.md`. |
| **Apply** | `openspec status --change <name>` / `openspec instructions tasks --change <name>` | `/opsx:apply-change` | Execute `tasks.md` checkbox-by-checkbox. |
| **Archive** | `openspec archive <name> --yes` | `/opsx:archive-change` | Merge delta into `specs/`, delete the change folder, log to `changes/archive/`. |

Also useful:
- `openspec status --change <name> --json` — artifact completion status.
- `openspec instructions <artifact> --change <name> --json` — enriched instructions for an artifact (`proposal`, `design`, `specs`, `tasks`, `apply`, `archive`).
- `openspec validate [name]` — check change/spec validity before archive.
- `openspec update --force` — refresh instruction/prompt files.

> **Headless note:** `openspec archive` (and `list`) need a TTY to pick a
> change interactively. In CI/non-interactive shells **always pass the name**:
> `openspec archive add-swarm-researcher --yes`.

---

## 3. `tasks.md` format (how apply tracks progress)

The apply phase parses checkbox format. Each task **must** be a checkbox and
should state how completion is verified:

```markdown
## 1. Setup

- [ ] 1.1 Create module and verify file exists
- [ ] 1.2 Add dependency and verify install succeeds

## 2. Core

- [ ] 2.1 Implement X and verify `pytest -k test_x` passes
```

- `[ ]` = pending, `[x]` = done. Apply reads these to report progress.
- Group under `## N.` headings; order by dependency.
- Put the verification *inside* the checkbox text.

---

## 4. Spec format (capabilities → requirements → scenarios)

A capability spec lists `## ADDED Requirements` (or `MODIFIED`/`REMOVED`).
Each requirement is a `SHALL` statement with executable `Scenario`s:

```markdown
## ADDED Requirements

### Requirement: Region detection for every race event
The system SHALL detect and assign a region for every race event.

#### Scenario: Region derived from display prefix
- **WHEN** an event has `en` starting with `"USA: Saratoga"`
- **THEN** the detected region is `"USA"`
```

Conventions we follow:
- New features → a **new capability** (`specs/<capability>/spec.md`).
- Modifications → `MODIFIED Requirements` in the existing capability.
- Requirements use `SHALL`/`SHALL NOT`; scenarios use `WHEN`/`THEN`.
- Keep the spec additive when possible — never silently change existing `SHALL`s
  without a `MODIFIED` entry.

---

## 5. Conventions at Strike Tips

1. **Read `project.md` first** — don't propose against guessed structure.
2. **One change = one feature.** Queue features one at a time; ask which to
   propose next rather than bundling.
3. **Agents must not bypass the change flow** for behavior changes — use the
   deltas, not ad-hoc edits to `core_agent/`.
4. **Tests are part of the change.** Every new requirement should be verifiable
   (pure functions + hermetic unit tests preferred). The Docker runtime
   (`docker exec strike-bot-new pytest core_agent/tests/`) is the verification
   gate — note `pytest-cov` is **not** installed in the container, so use plain
   `pytest`.
5. **Never commit secrets.** `.env` stays out of git; spec/docs may mention
   env-var *names* but never values.
6. **Archive only when green.** All `tasks.md` boxes checked and the relevant
   tests pass.

---

## 6. Worked example — `add-swarm-researcher` (archived 2026-08-29)

Lifecycle as actually executed:
1. `propose` → `openspec/changes/add-swarm-researcher/` with `proposal.md`,
   `design.md`, `specs/swarm-researcher/spec.md` (7 ADDED Requirements), `tasks.md`.
2. Implementation already lived in `core_agent/skills/swarm_researcher.py`
   (736 lines) + `adaptive_odds_monitor.py` wiring; the gap was missing unit
   tests. Added `core_agent/tests/test_swarm_researcher.py` (10 tests) and
   `test_news_linking.py` (7).
3. `apply` — marked all `tasks.md` boxes `[x]` as verified:
   `docker exec strike-bot-new pytest core_agent/tests/` → **54 passed**.
4. `archive add-swarm-researcher --yes` →
   - created `openspec/specs/swarm-researcher/spec.md` (7 requirements),
   - removed `openspec/changes/add-swarm-researcher/`,
   - logged `openspec/changes/archive/2026-08-29-add-swarm-researcher/`.
5. Committed `openspec/` to git (no code changes; 116K of markdown/yaml).

---

## 7. Current state

- **Canonical specs:** `swarm-researcher` (archived & accepted).
- **Active changes:** `core-value-bet-analyzer` (open — propose/apply pending).
- Run `openspec list` (or `openspec list --specs`) any time for the live view.

---

## 8. Quick reference

```bash
# Investigate
openspec list
openspec view

# Start / plan a change
openspec change new <kebab-name>        # or /opsx:propose
openspec instructions tasks --change <name> --json

# Track / build
openspec status --change <name> --json

# Close it out (headless — pass the name!)
openspec validate <name>
openspec archive <name> --yes

# Refresh tooling
openspec update --force
```

*Last updated: 2026-08-29 — OpenSpec v1.11.0.*
