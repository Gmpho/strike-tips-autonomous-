import modal
import os
from pathlib import Path

# 1. Image Definition
# Consistent with local environment requirements
image = (
    modal.Image.debian_slim()
    .apt_install("curl")
    .pip_install(
        "httpx",
        "beautifulsoup4",
        "python-telegram-bot",
        "google-generativeai",
        "anthropic",
        "openai",
        "fastapi",
        "uvicorn",
        "pydantic",
        "schedule",
    )
)

# 2. App & Storage
app = modal.App("strike-tips-racing")
# Volume to mirror your /data directory in the cloud
data_volume = modal.Volume.from_name("strike-tips-data", create_if_missing=True)

# 3. Secrets
secrets = [
    modal.Secret.from_name("strike-tips-secrets"),
    modal.Secret.from_name("strike-tips-api-key"),
]


# 4. Shared Task Logic
def get_shared_args():
    return {
        "image": image,
        "secrets": secrets,
        "volumes": {"/app/data": data_volume},
        "memory": 1536,
        "timeout": 3600,
    }


@app.function(**get_shared_args())
def run_scan():
    """Execute the strike-tips scan task in the cloud."""
    import subprocess

    print("🚀 Starting Strike Tips Scan on Modal...")
    # Trigger the same logic used in docker-compose
    result = subprocess.run(
        ["python3", "core_agent/core/strike_tips.py", "scan"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    return {"status": "complete"}


@app.function(**get_shared_args())
@modal.asgi_app()
def serve_api():
    """Host the FastAPI backend on Modal."""
    from core_agent.api import app as fastapi_app

    return fastapi_app
