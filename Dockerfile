FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/.cache/torch
ENV PIP_PREFER_BINARY=1
ENV PIP_TIMEOUT=600

WORKDIR /app

# Upgrade pip first (backtracking fixes in newer pip)
RUN pip install --no-cache-dir --upgrade pip "setuptools<75"

# Install agent-framework with --no-deps to avoid core-orchestrations version conflict
# (agent-framework==1.0.0rc4 requires agent-framework-core==1.0.0rc4, but
#  agent-framework-core[all] pulls orchestrations which demands core>=1.9.0)
RUN pip install --timeout=600 --retries=5 \
    --no-deps \
    agent-framework==1.0.0rc4 \
    agent-framework-core==1.0.0rc4 \
    agent-framework-openai==1.0.0

# Install everything else
COPY requirements.txt .
RUN sed -i '/^agent-framework/d; /^openai/d' requirements.txt \
 && pip install --timeout=600 --retries=5 --default-timeout=600 -r requirements.txt

# Install openai separately (no conflict)
RUN pip install --timeout=600 --retries=5 openai==2.30.0

# OpenTelemetry semantic conventions for AI (needed by agent-framework tracing at runtime)
RUN pip install --timeout=600 --retries=5 opentelemetry-semantic-conventions-ai

# Install Playwright system dependencies
RUN playwright install-deps chromium 2>&1 || echo "System deps install failed"

# Pre-download Playwright browsers at build time (CDN is reachable from buildkit now)
RUN playwright install chromium 2>&1 || echo "Playwright browsers pre-download failed — will retry at runtime"

# Pre-download ChromaDB ONNX embedding model (all-MiniLM-L6-v2, ~79MB)
COPY prewarm_chroma.py .
RUN python prewarm_chroma.py 2>&1 || echo "Chroma ONNX pre-download failed — will download at startup"

# Copy project files
COPY . .

# Expose port
EXPOSE 8000

# Run as root for host-mounted volume compatibility
USER root

CMD uvicorn core_agent.api_pkg:app --host 0.0.0.0 --port 8000
