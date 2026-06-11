FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/.cache/torch

WORKDIR /app

# Install Python requirements (no --no-cache-dir: pip cache survives rebuilds, ~10x faster)
COPY requirements.txt .
RUN pip install --timeout=300 --retries=5 --default-timeout=300 -r requirements.txt

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
