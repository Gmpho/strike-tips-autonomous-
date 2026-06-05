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
RUN pip install -r requirements.txt

# Install Playwright system dependencies (libglib2.0, libnss3, etc.)
RUN playwright install-deps chromium 2>&1 || echo "System deps install failed — will retry at runtime"

# Copy project files
COPY . .

# Expose port
EXPOSE 8000

# Run as root for host-mounted volume compatibility
USER root

# Install browsers at runtime (CDN is reachable from containers but not Docker build daemon)
CMD playwright install chromium 2>&1 || true && uvicorn core_agent.api:app --host 0.0.0.0 --port 8000
