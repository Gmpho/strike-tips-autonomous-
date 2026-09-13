## Context

D1 froze Jun-2026 when its writer was refactored away; KV snapshot ingest 500s daily once the ~130-put fan-out burns the 1k/day write quota (~01:00); tonight's rotation exposed a stale second key 401ing pushes (fixed by STRIKE-first + 401 retry).

## Goals / Non-Goals

**Goals:** fresh D1 (cards + results), KV alive all day, key discipline that survives rotations.

**Non-Goals:** backfilling Jun-Sep history (archive stays; ChromaDB carried memory); changing push cadence.

## Decisions

* Single-key discipline: STRIKE key canonical, worker BACKEND_API_KEY kept equal, legacy CF var override-only + 401 retry. Rotation procedure: one value everywhere.
* Mirror writes are fire-and-forget inside scans/settles (10s timeout, debug-log only).
* Doc IDs deterministic (`card-{date}-{track}-r{n}`, `result-{date}-{track}-r{n}-{bet_id}`) so re-runs upsert via INSERT OR REPLACE.
* Write-gate by exact string compare (no hashing infra needed at this size).
* Tonight's remaining 500s are quota exhaustion until UTC midnight, not code — verify Monday: KV populated + no 500s + D1 row growth.
