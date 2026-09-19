## Why

This repo declares OpenSpec the source of truth, yet the store currently fails its own gate and contradicts the running system:

1. **Every active delta is unparseable.** All four active changes report `✓ Complete`, but each one's delta opens with `### ADDED Requirements` (heading level 3). The validator requires `## ADDED Requirements` at level 2, so **zero deltas parse** and `openspec validate` fails with `No delta sections found`. Four implemented capabilities therefore cannot be promoted into `openspec/specs/`.
2. **One concern, two capabilities.** `cloud-models` (from `refactor-cloud-models`) and `cloud-models-correction` (inside `stabilize-sep-ops`) describe the same subject — the very fragmentation this store exists to prevent.
3. **Model identifiers have three disagreeing sources of truth.** `refactor-cloud-models/tasks.md` prescribes Groq `llama-3.3-70b-versatile`; `docs/CLOUD_MODELS.md` states that pool is production `openai/gpt-oss-120b`/`20b` and that Llama 3.3/3.1 were **retired**; `agent/providers/task_router.py` accepts all of the former plus `gemini-2.5-*`. `CLOUD_MODELS.md` itself records that exactly this mismatch previously made every call 404 into paid fallback spend.
4. **Documentation describes a platform we no longer run.** The HUD is served from Cloudflare Pages, but 44 tracked files mention Vercel: `AGENTS.md` calls it the "Vercel HUD", documents `vercel deploy --prod`, claims `vercel.json` provides the SPA rewrite and that `middleware.ts` handles API routing. That middleware is **inert on Pages** (Pages uses `functions/_middleware.ts`, which does not exist). `vercel.json`, `middleware.ts` and two `.vercel/` directories remain in version control.
5. **State and metrics are stale.** `openspec/project.md` asserts "No active change folders remain" (four are active); `docs/openspec-usage.md §7` lists only `swarm-researcher` as canonical and `core-value-bet-analyzer` as the sole open change; three documents quote test counts of 30 or 44 while the suite collects **261**.

Net effect: an agent obeying the repo's own "read the Brain first" rule is instructed to deploy to the wrong platform and to trust model IDs that are documented as retired. This change is deliberately limited to governance, documentation, and the spec store — no runtime behaviour changes.

## What Changes

- Repair the four active deltas to the validator's format (`## <OP> Requirements` at h2, `### Requirement:` per requirement, at least one `#### Scenario:` each), so `openspec validate` passes and the capabilities can be archived.
- Merge `cloud-models-correction` into the pre-existing `cloud-models` capability so the subject has one capability name.
- Establish a single authoritative list of permitted cloud model identifiers and reconcile `docs/CLOUD_MODELS.md`, `core_agent/agent/providers/task_router.py` and the `start.sh` warm-up model against it.
- Retire the Vercel path: delete `strike-tips-hud/middleware.ts`, `strike-tips-hud/vercel.json`, `strike-tips-hud/.vercel/` and `.vercel/`, and rewrite the platform story across `AGENTS.md`, `README.md` and `docs/` to name Cloudflare Pages only.
- Add `docs/DEPLOY.md` as the single deployment truth (Pages build/output, Worker deploy, Modal deploy) and remove the competing deploy instructions.
- Correct stale facts: collected test count, canonical spec list, and active-change state.
- Archive the four completed changes once their deltas validate.

## Capabilities

### New Capabilities

- `spec-governance`: the contract that keeps the spec store trustworthy — deltas stay parseable and validatable, one subject maps to one capability, cloud model identifiers have a single authoritative source, documented platform facts match the platform actually serving traffic, and documented metrics are reproducible from repository tooling.

### Modified Capabilities

- None. This change introduces no spec-level behaviour change to an existing canonical capability; the `cloud-models` consolidation is completed by archiving the sibling changes after their deltas validate.

## Impact

- **Spec store**: `openspec/changes/{stabilize-sep-ops,refactor-cloud-models,gemini-groq-chat-agents,gemini-groq-tts}` (format repair), `openspec/changes/archive/` (four new archive entries), `openspec/specs/` (four capabilities promoted, plus new `spec-governance`), `openspec/project.md`.
- **Documentation**: `AGENTS.md`, `README.md`, `docs/openspec-usage.md`, `docs/CLOUD_MODELS.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOY.md` (new); Vercel references removed across tracked docs.
- **Deleted files**: `strike-tips-hud/middleware.ts`, `strike-tips-hud/vercel.json`, `strike-tips-hud/.vercel/`, `.vercel/`.
- **Code**: none. No change to runtime behaviour, API surface, money path, or bankroll governance. The only code-adjacent edits are doc-truth reconciliation of a model warm-up string and a provider alias tuple, which are behaviour-preserving and verified by existing tests.
- **Risk**: low. Archiving is reversible via git; deleting dead Vercel files removes a latent trap (a re-enabled Vercel deployment would proxy state-changing writes with the master key, guarding only `/api/agent/{kill,reset}`).
