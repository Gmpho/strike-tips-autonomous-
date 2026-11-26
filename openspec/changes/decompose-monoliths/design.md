## Context

See `proposal.md` for motivation and the three capability specs for the
behavioural contract. The measured starting point is:

```
strike_tips.py            3982 lines   scans + parsing + exotics + betting facade
adaptive_odds_monitor.py  2963 lines   clock + merges + ATR + caches + cycle loop
betway_api.py             1442 lines   transport + daily cache + KV bridge + parser
index.ts                   993 lines   REST + MCP + caches + budgets + cron
AIChat.tsx                1423 lines   (deferred to a later change)
```

Fourteen test modules and five production modules import private helpers
directly from the two Python monoliths. Several tests also monkeypatch
module-level names (for example `MARKET_SNAPSHOT_PATH` on the monitor and
snapshot writer modules). `snapshot_writer` imports `_close_overdue_races` from
the monitor, so a careless move creates a circular import. These three facts,
not aesthetics, drive the design.

## Goals / Non-Goals

**Goals:**

- Make each concern independently readable and testable, with one orchestrator
  per layer that owns lifecycle and orchestration only.
- Preserve every observable contract: imports, snapshots, routes, bindings, KV
  keys, MCP tools, protected paths and test coverage.
- Make upstream failure text accurate while touching that code, so the 26 Nov
  class of "403 that lies" cannot recur.

**Non-Goals:**

- No new feature, no new dependency, no schema or API change, no model change.
- No change to settlement math, bankroll ledger, cron/volume configuration, or
  the protected paths listed in the proposal.
- No renaming for style alone, no deleting "dead" code without a characterising
  test and explicit sign-off.
- HUD `AIChat.tsx` is deferred to a separate change.

## Decisions

### 1. Facade modules with verbatim re-exports

The original modules stay at their paths and re-export every moved symbol.
Callers and tests keep importing from where they always have.

- *Alternative:* rewrite all imports across 19 modules. Rejected: most of those
  callers are protected tests, and a mechanical rewrite is exactly the kind of
  net-negative diff that hid earlier regressions.
- *Rule:* a moved helper is copied verbatim first; naming/style cleanup, if
  any, is a separate later change.

### 2. Helpers are pure and take injected inputs

Extracted helpers receive paths, timestamps and clients as parameters. They
do not read or patch module-level constants owned by the facade, and they do
not import the orchestrator.

- *Reason:* tests monkeypatch `MARKET_SNAPSHOT_PATH` on the original module. If
  a helper captured a constant in a new module, those patches would silently
  stop working while tests still passed against the wrong file.
- *Consequence:* the facade passes its (possibly patched) module globals into
  helpers explicitly.

### 3. Break the snapshot-writer / monitor cycle explicitly

`snapshot_writer` currently imports `_close_overdue_races` from the monitor.
The off-time logic moves to a dependency-free module; both the monitor facade
and `snapshot_writer` import it from there. Neither helper module imports
`snapshot_writer` at module scope.

### 4. Orchestrator owns all side effects

Only the orchestrator registers schedules, starts loops, writes the published
snapshot, emits telemetry/digests and commits volumes. Helper modules perform
calculation and in-memory transformation only.

### 5. Worker split keeps one router

`index.ts` remains the sole `export default` and route table. Handlers move into
route modules that receive `(request, url, env, ctx)`. The traffic-triggered
price refresh, its 8-minute throttle, hourly cron and all KV keys stay exactly
where they are. No new npm dependency.

### 6. Staged, test-first execution

Each phase: characterisation tests → verbatim move → re-export → Docker suite →
one commit. No phase may reduce priced runners, remove tests or change a
snapshot field. Deployment is a separate, explicit action after the whole
change is green.

### 7. Diagnostics are centralised and factual

One diagnostics text source per layer. Every upstream refusal reports the real
refusing layer, status and colo when known. A path that produced no stored
payload is never called the production fetch. HUD-facing strings stay generic.

## Risks / Trade-offs

- **[Two names for one helper] →** facade re-exports are intentional technical
  debt; document them as the compatibility layer and never add new callers to
  the old private name.
- **[Circular import after move] →** dependency-free time module; import graph
  checked with a cold `python -c "import ..."` in Docker after each phase.
- **[Monkeypatched constants stop working] →** inject path/time/client as
  arguments; keep an explicit test that patches the facade and observes the
  helper using the patched value.
- **[Large diff hides a regression] →** verbatim moves, one phase per commit,
  `git diff --stat` reviewed against the phase, no unrelated reformatting.
- **[Price/form drift] →** before/after snapshot fixture comparison and the
  existing 1,100+ test suite must both pass in Docker before deploy.
- **[Worker route parity] →** route table snapshot test listing every path and
  method before the split; compare after.
- **[KV write budget] →** the traffic trigger's 8-minute throttle and hourly
  cron are preserved and asserted, not optimised during this change.

## Migration Plan

1. Phase 0 — capture route inventory and snapshot fixtures; add missing
   characterisation tests (add-only).
2. Phase 1 — off-time / outage / card-hygiene helpers out of the monitor.
3. Phase 2 — fallback merge and spine helpers out of the monitor.
4. Phase 3 — ATR freshness helpers out of the monitor.
5. Phase 4 — scan inputs, exotics and value helpers out of `strike_tips`,
   with facade methods delegating so `StrikeTips.*` signatures stay intact.
6. Phase 5 — Worker route modules and centralised diagnostics text.
7. Verify: `docker exec strike-bot-new python -m pytest core_agent/tests/ -q`
   and `npm test` / `npx tsc --noEmit` for the Worker; live card, /picks and
   KV key probes unchanged.
8. Deploy only on explicit request: Modal for Python, Wrangler for the Worker.
   Rollback is reverting the phase commit and redeploying the previous version.

## Open Questions

- Should `AIChat.tsx` (1,423 lines) get its own change next, or be folded into a
  later frontend-focused change? (Does not affect this change's specs or tasks.)
- Should the several stale in-progress OpenSpec changes be archived first as a
  separate governance task? (Independent of this change.)
- Should post-extraction renaming/formatting be a follow-up change rather than
  part of any phase? (Recommended: yes.)
