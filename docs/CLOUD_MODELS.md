# Cloud Models — Live-Verified Pools, TPM Budget, Fallbacks

Sep-2026 lesson: a refactor pinned model IDs that no longer exist on the
provider (Groq retired Llama 3.3/3.1 + DeepSeek; Gemini retired 2.0/1.5).
Every call 404'd into fallback spend. **Verify IDs against the live
`/models` lists before changing them.**

## Production pools (live-verified Sep-2026)

| Provider | Flagship / tools | Fast / light | Deep |
|---|---|---|---|
| Groq | `openai/gpt-oss-120b` | `openai/gpt-oss-20b` | `openai/gpt-oss-120b` |
| Gemini | `gemini-2.5-flash` | `gemini-2.5-flash-lite` | `gemini-2.5-pro` (cards), `gemini-3.1-pro-preview` (chat math) |

Also live: `gemini-3.5-flash`, `gemini-3.1-flash-lite`, Groq `whisper-large-v3`
(+turbo), `gemini-2.5-flash-preview-tts`. Unverified: `gemini-3.8-live`
(Live API has no list endpoint — confirm in console before relying on it).

Check current availability any time (free, read-only):

```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]"
```

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
