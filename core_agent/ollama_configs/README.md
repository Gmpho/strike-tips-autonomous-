# Ollama Modelfiles for Racing Bot

This folder contains optimized Modelfiles for Strike Tips with gambling-free prompts.

## Model Specialties

| Model | Base Model | Specialty | Speed |
|-------|-----------|----------|-------|
| `racing_llama` | llama3.2:1b | Router + Synthesizer | Fast |
| `racing_qwen` | qwen3.5:0.8b | Fast Reads | ~1-2s |
| `func_gemma` | functiongemma:270m | Write Operations | ~1-2s |
| `lfm_racing` | lfm2.5-thinking:latest | Deep Analysis | ~2-3s |
| `ds_racing` | deepseek-r1:1.5b | Reasoning | Variable |

## Installation

Run these commands in your terminal (in this folder):

```powershell
# Install all optimized models
ollama create racing_qwen -f racing_qwen.Modelfile
ollama create ds_racing -f ds_racing.Modelfile
ollama create lfm_racing -f lfm_racing.Modelfile
ollama create racing_llama -f racing_llama.Modelfile
ollama create func_gemma -f func_gemma.Modelfile
```

## Verify

After installing, check with:
```powershell
ollama list
```

## Tool Names (11 Tools)

All models use these gambling-free tool names:
- `evaluate_race` - Analyze race for value
- `calculate_probability_edge` - Calculate edge percentage
- `get_account_summary` - Check balance
- `record_selection` - Record a selection
- `update_race_result` - Update result
- `calculate_max_position` - Calculate max stake
- `search_past_races` - Search memory
- `search_racing_data` - Web search
- `verify_race_exists` - Verify race
- `run_daily_analysis` - Scan races
- `get_odds_snapshot` - Get odds

## Memory Optimization (16GB RAM)

| Setting | Value | Why |
|---------|-------|-----|
| num_ctx | 1024 | Smaller context = less RAM |
| num_predict | 256 | Prevents long outputs |
| temperature | 0.1-0.3 | Less hallucination |
| num_thread | 3 | Leaves CPU for OS |
