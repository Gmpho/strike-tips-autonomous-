#!/usr/bin/env bash
# Deploy core_agent FastAPI to Google Cloud Run as a Modal fallback/bridge.
#
# Prerequisites:
#   1. gcloud CLI installed + authenticated:
#        gcloud auth login
#        gcloud auth application-default login
#   2. GCP project selected:  gcloud config set project <PROJECT_ID>
#   3. APIs enabled (script does this): run, cloudbuild, artifactregistry
#
# Usage:
#   ./deploy-cloud-run.sh <PROJECT_ID> [REGION]
#
# Notes:
# - Builds from the repo Dockerfile via Cloud Build (no Terraform needed).
# - min-instances=1 keeps the odds monitor / swarm researcher / heartbeat
#   loops alive 24/7 (~$10-15/mo). Use MIN_INSTANCES=0 for pure free-tier
#   scale-to-zero (API works on demand, background loops pause when idle).
# - Redis-dependent features degrade gracefully without REDIS_URL; point it
#   at Upstash free tier to keep full pubsub/task-queue function.

set -euo pipefail

PROJECT_ID="${1:?Usage: ./deploy-cloud-run.sh <PROJECT_ID> [REGION]}"
REGION="${2:-europe-west1}"
SERVICE="strike-tips-api"
MIN_INSTANCES="${MIN_INSTANCES:-0}"   # set MIN_INSTANCES=1 for always-on monitoring
ENV_FILE=".env"

echo "==> Enabling required APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com --project "$PROJECT_ID"

echo "==> Building env-var flags from $ENV_FILE (non-secret vars)..."
ENV_VARS="PYTHONPATH=/app,DATA_DIR=/app/data,PAPER_TRADING=true"
if [ -f "$ENV_FILE" ]; then
  # Pass through safe non-sensitive config; secrets go via --set-secrets or remain unset.
  for key in TELEGRAM_CHAT_ID MODEL_ORCHESTRATOR MODEL_REASONER MODEL_SCRAPER \
             MODEL_FUNC_CALL MODEL_THINKING MODEL_FAST_LOCAL OLLAMA_HOST \
             CHROMA_HOST CHROMA_DATABASE CHROMA_API_KEY; do
    val=$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- || true)
    if [ -n "${val:-}" ]; then ENV_VARS="$ENV_VARS,$key=$val"; fi
  done
fi

echo "==> Deploying $SERVICE to $REGION (min-instances=$MIN_INSTANCES)..."
gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --port 8000 \
  --memory 2Gi \
  --cpu 1 \
  --min-instances "$MIN_INSTANCES" \
  --max-instances 3 \
  --timeout 3600 \
  --concurrency 80 \
  --allow-unauthenticated \
  --set-env-vars "$ENV_VARS"

URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" \
  --region "$REGION" --format 'value(status.url)')

echo ""
echo "✅ Deployed: $URL"
echo ""
echo "Next steps:"
echo "  1. Set secrets (recommended over env vars for keys):"
echo "     echo -n \"\$GROQ_API_KEY\" | gcloud secrets create groq-api-key --data-file=- --project $PROJECT_ID"
echo "     gcloud run services update $SERVICE --region $REGION --project $PROJECT_ID \\"
echo "       --update-secrets=GROQ_API_KEY=groq-api-key:latest"
echo "  2. Opt the HUD into this fallback (Modal stays primary) by setting in Vercel env vars:"
echo "     BACKEND_FALLBACK_ORIGIN=$URL"
echo "     VITE_SSE_FALLBACK_ORIGIN=$URL"
echo "  3. Re-point the Telegram webhook during any Modal outage:"
echo "     curl \"$URL/telegram-webhook/register\" # or your register_webhook job"
