FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/.cache/torch

WORKDIR /app

# Install Python requirements (no --no-cache-dir: pip cache survives rebuilds, ~10x faster)
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt


# Pre-install browsers (included in base, but ensuring for current version)
RUN playwright install chromium

# Copy project files
COPY . .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app /root/.cache

# Expose port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Run FastAPI
CMD ["uvicorn", "core_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
