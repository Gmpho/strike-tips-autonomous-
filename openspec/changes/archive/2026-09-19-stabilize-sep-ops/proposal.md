# Proposal: Stabilize September Ops (Settlement Truth + Chat Grounding + Prod Survival)

## Why

Two production incidents plus a validation pass exposed gaps no spec covered:

1. **Outage (18 Sep morning)** — `serve_api` crash-looped overnight (cold init
   past the 120s limit on a multi-GB image, no warmer after the keep-warm cron
   was cut). Every web container also ran a full monitor/swarm/heartbeat loop,
   fork-bombing CPU, burning Groq quota, and starving the event loop until HTTP
   hung. HUD showed offline; data froze at keeper startup (in-memory snapshot
   never refreshed — the Redis subscriber was a dead letter).
2. **Settlement gaps** — scratched horses could be scored WON/LOST; abandoned
   meetings (Greyville) left singles PENDING with no refund path; exotic
   tickets were all-outsider lottery lines.
3. **Chat hallucinations** — fallthrough answers invented tracks ("Rand
   Stadium", "Ohlange"), dates, and full cards when the snapshot was empty
   or unmatched.
4. **Dead model IDs** — `refactor-cloud-models` prescribed IDs retired by the
   providers (Groq Llama 3.3/3.1 + DeepSeek gone; Gemini 2.0/1.5 gone),
   verified against the live `/models` lists. Every call 404'd into fallback
   spend. Its proposal/spec premise is inverted and needs correction.

## What Changes (all implemented + tested)

- Settlement voids: non-runner auto-VOID (refund), abandoned-meeting VOID
  for singles (refund + Telegram note), exotic build guards (phantom /
  balance / NR), place capture (`placed`, `place_rate`), form-driven ticket
  budget (24/16/10).
- Prod survival: slim web lifespan (no monitor/swarm/heartbeat/worker in
  web), keeper `min_containers=1`, 300s init allowance, 512MB, monitor
  warm-ping + intelligence piggyback (cron cap respected), digest flush
  before cron exit, prompt diet (saves the 8k TPM ceiling), snapshot disk
  refresh, HUD `isFinished` filter, decoupled telemetry/news poll,
  `VITE_BACKEND` local/prod switch + LOCAL badge.
- Chat grounding: existence gate, date+meetings injection, pasted-card
  passthrough (`task_router.py`).
- Model pools corrected to live-verified IDs; Telegram `/model` mirrors HUD.
- Memory: Honcho ID sanitizer, Chroma retry-then-soft-fail.
- 40+ new tests (governor budget/places, settlement chain, cloud routing /
  fallback / prompt budgets / grounding / abandonment / memory / telegram).

## Non-goals

- Exotic abandoned-leg tote rules (tickets stay PENDING; follow-up).
- Slim browser-free `serve_api` image (proper cold-start fix; follow-up).
- `gemini-3.8-live` verification (no list endpoint; cloud-agent owned).
