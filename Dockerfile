FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/.cache/torch

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt pypdf


# Pre-install browsers (included in base, but ensuring for current version)
RUN playwright install chromium

# Copy project files
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "core_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
