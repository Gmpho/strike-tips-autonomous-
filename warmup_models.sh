#!/bin/bash
# Warm up all racing models so they're ready in memory
# Run once after docker compose up

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

echo "⏳ Warming up racing models..."

for model in func_gemma racing_llama racing_qwen lfm_racing ds_racing; do
  echo -n "→ $model: "
  result=$(curl -s -X POST "$OLLAMA_HOST/api/chat" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false,\"think\":false,\"options\":{\"num_predict\":1,\"num_keep\":0}}" \
    --max-time 300 2>&1)
  if echo "$result" | grep -q '"content"'; then
    echo "✅ ready"
  else
    err=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','?')[:60])" 2>/dev/null || echo "timeout")
    echo "❌ $err"
  fi
done

echo "✅ Warmup complete"
