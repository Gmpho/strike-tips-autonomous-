# Tasks — stabilize-sep-ops (all complete, verified)

## 1. Settlement truth

- [x] 1.1 Non-runner pipeline: Betfair REMOVED + Betway nonRunner → merge flag + injection → settlement VOID with refund
- [x] 1.2 Abandoned-meeting detection (dark board +90min grace) → VOID PENDING singles, refund, Telegram note, D1-excluded
- [x] 1.3 Exotic build guards: phantom-meeting, balance (≥half legs ≤6.0), NR filter + strategist prompt rule
- [x] 1.4 Place capture (`placed` on settle, ATR lookup) + `place_rate()`
- [x] 1.5 Form-driven ticket budget (24/16/10 over last-20) in both auto loops + tests

## 2. Prod survival

- [x] 2.1 Slim web lifespan (drop monitor.run/swarm/heartbeat/worker/warmup; Redis-gated worker/subscriber)
- [x] 2.2 Keeper `min_containers=1`, `max_containers=1`, 512MB, `startup_timeout=300`
- [x] 2.3 Monitor warm-ping (correct `/api/system/health` route) + intelligence piggyback every 6th tick
- [x] 2.4 Digest `flush()` before cron container exit (261 fired / 0 sent incident)
- [x] 2.5 Prompt diet (`_slim_race_for_prompt`) + 413-fails-fast, 429-once semantics
- [x] 2.6 Snapshot disk-mtime refresh (60s) + HUD `isFinished` ingestion filter
- [x] 2.7 Decoupled telemetry/news slow poll (not hash-gated)
- [x] 2.8 `VITE_BACKEND` local/prod switch (default local) + LOCAL/PROD badge

## 3. Chat grounding + models + memory

- [x] 3.1 Existence gate + date/meetings injection + pasted-card passthrough
- [x] 3.2 Live model audit; correct pools to verified IDs (Groq gpt-oss, Gemini 2.5 chain)
- [x] 3.3 Telegram `/model` mirrors HUD pool; every key resolves in router tuples
- [x] 3.4 Honcho ID sanitizer (`^[a-zA-Z0-9_-]+$`); Chroma retry-then-soft-fail
- [x] 3.5 News image proxy hosts for SA feeds; vite `process.env` backfill for server services

## 4. Validation

- [x] 4.1 Full suite green locally (243+) and in Docker (245), `tsc` clean
- [x] 4.2 Live probes: refusal path, NR validators, Honcho peer init, dev-proxy local chain
- [x] 4.3 Key audit: no secrets in client bundle, `.env` never committed
