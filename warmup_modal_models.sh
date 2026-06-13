#!/bin/bash
# Warm up Modal Ollama models after deploy
# Run: modal run core_agent.core.modal_app::pull_ollama_models
# Then run this to verify they're ready

OLLAMA_HOST="${OLLAMA_HOST:-https://gmpho--strike-tips-ollama-cloud-ollama.modal.run}"

echo "⏳ Warming up Modal Ollama models at $OLLAMA_HOST..."

for model in functiongemma:270m qwen3.5:0.8b embeddinggemma:300m; do
  echo -n "→ $model: "
  result=$(curl -s -X POST "$OLLAMA_HOST/api/chat" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false,\"options\":{\"num_predict\":1,\"num_keep\":0}}" \
    --max-time 120 2>&1)
  if echo "$result" | grep -q '"content"'; then
    echo "✅ ready"
  else
    err=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','?')[:60])" 2>/dev/null || echo "timeout")
    echo "❌ $err"
  fi
done

# Verify embeddings endpoint
echo -n "→ embeddinggemma:300m (embeddings): "
result=$(curl -s -X POST "$OLLAMA_HOST/api/embeddings" \
  -H "Content-Type: application/json" \
  -d '{"model":"embeddinggemma:300m","prompt":"test"}' \
  --max-time 60 2>&1)
if echo "$result" | grep -q '"embedding"'; then
  echo "✅ ready"
else
  err=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error','?')[:60])" 2>/dev/null || echo "timeout")
  echo "❌ $err"
fi

echo "✅ Warmup complete"