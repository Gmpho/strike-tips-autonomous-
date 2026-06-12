# Ollama Modelfiles — Strike Tips Racing Bot

Architecture-aligned Modelfiles. Each model has a specific role in the TaskRouter pipeline.

## Model Roles

| Model | Base Model | Format | Role | Used For (TOOL_INFO specialists) |
|-------|-----------|--------|------|----------------------------------|
| `racing_qwen` | `llama3.2:1b-text-q4_K_M` | generate | Racing analysis + chat | calculate_probability_edge, calculate_max_position, get_account_summary, search_past_races, verify_race_exists, get_odds_snapshot, get_atr_*, get_dream_context, search_racing_keywords, search_hybrid, save_learned_insight |
| `racing_llama` | `llama3.2:1b-text-q4_K_M` | generate | Search results summarizer | search_racing_data |
| `lfm_racing` | `lfm2.5-thinking:latest` | generate | Deep reasoning (thinking model) | evaluate_race, run_daily_analysis |
| `ds_racing` | `deepseek-r1:1.5b-qwen-distill-q4_K_M` | generate | Structured reasoning (thinking model) | (reserve — not yet routed by TaskRouter) |
| `func_gemma` | `functiongemma:270m` | generate | Tool-aware specialist | record_selection, update_race_result |

**Runtime models** (not created via Modelfiles):
| `functiongemma:270m` | `functiongemma:270m` | chat | Tool calling fallback | TaskRouter Phase 2 |
| `qwen3.5:0.8b` | `qwen3.5:0.8b` | chat | General chat fallback | TaskRouter Phase 4 |

## Architecture Notes

### `api_format` matters
- **generate** (`/api/generate`): completion-style — prompt only, no tool definitions. Used for specialist models that respond to simple Q&A.
- **chat** (`/api/chat`): structured messages with optional tool definitions. Used for model that need tool calling (`functiongemma:270m`) or multi-turn chat (`qwen3.5:0.8b`).

### Thinking models
`lfm_racing` and `ds_racing` are thinking/reasoning models. They produce `<think>...</think>` tokens which are stripped server-side by `OllamaProvider.stream()` before sending to the client. These models should NOT have tool calling in their system prompts — structured JSON output inside think blocks gets lost.

### Tool knowledge stays in the system prompt
TaskRouter does NOT pass tool definitions to local models (tools=None). Models learn about available tools only through their system prompt. `func_gemma` has the full 18-tool list; other models don't need it.

## Recreate Models

```bash
# From this directory:
ollama create racing_qwen -f racing_qwen.Modelfile
ollama create racing_llama -f racing_llama.Modelfile
ollama create lfm_racing -f lfm_racing.Modelfile
ollama create ds_racing -f ds_racing.Modelfile
ollama create func_gemma -f func_gemma.Modelfile
```

## Verify

```bash
ollama list
ollama show racing_qwen:latest  # check SYSTEM and PARAMETER
```

## Resource Constraints (2 CPU cores, 4 GB RAM)

| Model | Size | Cold-start | Notes |
|-------|------|-----------|-------|
| `functiongemma:270m` | 300 MB | ~51s | Fastest load, tool calling |
| `func_gemma:latest` | 300 MB | ~51s | Same base, specialist system prompt |
| `lfm_racing:latest` | 731 MB | ~5.3 min | Thinking model |
| `racing_qwen:latest` | 807 MB | ~5.8 min | General analysis |
| `racing_llama:latest` | 807 MB | ~5.8 min | Search summarizer |
| `ds_racing:latest` | 1.1 GB | ~8 min | Deep reasoning |
| `qwen3.5:0.8b` | 1.0 GB | ~19 min | Cold-start heavy |
| `embeddinggemma:300m` | 621 MB | ~45s | Embeddings only |
| `llama3.2:1b` | 1.3 GB | ~6 min | Unused by TaskRouter |
| `deepseek-r1:1.5b` | 1.1 GB | ~8 min | Unused |
