# Cloud Models — Single Source of Truth

**The authoritative pool lives in the spec: [`openspec/specs/cloud-models/spec.md`](../openspec/specs/cloud-models/spec.md).**

This document is a *pointer* plus the operational context that does not belong in a behaviour spec: how to re-verify the pool, and the budget rules that keep spend sane. Do **not** add a second model table here — a duplicated list is exactly what drifted out of sync before.

Sep-2026 lesson: a refactor pinned model IDs that no longer exist on the
provider (Groq retired Llama 3.3/3.1 + DeepSeek; Gemini retired 2.0/1.5).
Every call 404'd into fallback spend, and the change's own premise ended up
inverted against the live lists. **Verify IDs against `/models` before
changing them.**

## Re-verifying the pool (free, read-only)

```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" \
  | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"

curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" \
  | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]"
```

Record the probe date in the spec's Purpose block after each re-probe. An
identifier whose API exposes no enumeration endpoint — the Live API's
`gemini-3.8-live` — stays marked **unverified** in the spec rather than being
promoted to authoritative.

## TPM budget (the 413/429 incident)

Groq `on_demand` tier caps at **8000 TPM**. Full asdict race cards with
12-field Betfair enrichment hit 9–14k tokens/call → `413 Request too large`
+ `429`s with paid Gemini fallbacks. Rules:

- Per-race value prompts use the slim projection only
  (`_slim_race_for_prompt`: track/number/distance/condition + ≤14 runners ×
  horse/odds/form/jockey/trainer) — ≈60–70% smaller, asserted by
  `test_prompt_budgets.py` (<1500 est. tokens/race).
- 413s surface immediately (no retry — `test_413_surfaced_immediately`);
  the fix is a smaller prompt, never more retries. 429s retry once, max.
- Batching stays at 6 races/call; keep total call size under ~6k tokens.

## Fallback chains

- Chat/scan: Groq → Gemini (`GEMINI_CHAIN`), then Ollama local.
- Telegram `/model`: `auto` · `groq` · `gemini` · `gemini-pro` · `gemini-lite`
  (mirrors the HUD selector; every key resolves in `task_router` override
  tuples — `test_telegram_models.py` fails the build otherwise).
- Embeddings: local Ollama → Gemini → ChromaDB default.
