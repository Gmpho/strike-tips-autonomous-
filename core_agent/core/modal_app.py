
import modal
import os

# Define the image based on your existing Dockerfile
# This ensures consistency between local Docker and Modal Cloud
image = modal.Image.from_dockerfile("Dockerfile")

app = modal.App("strike-tips-racing")

# Define secrets for API keys (must be created in Modal dashboard)
# e.g., modal secret create strike-tips-secrets GEMINI_API_KEY=... GROQ_API_KEY=...
secrets = [modal.Secret.from_name("strike-tips-secrets")]

@app.function(
    image=image,
    secrets=secrets,
    # Use 1.5G memory to match odds-monitor limit
    memory=1536,
    # Allow 1 hour execution for scans
    timeout=3600,
)
def run_scan():
    """Execute the strike-tips scan task in the cloud."""
    import subprocess
    print("🚀 Starting Strike Tips Scan on Modal...")
    # Trigger the same logic used in docker-compose
    result = subprocess.run(
        ["python3", "core_agent/core/strike_tips.py", "scan"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    return {"status": "complete"}

@app.function(
    image=image,
    secrets=secrets,
    ports={8000: 8000}
)
@modal.asgi_app()
def serve_api():
    """Host the FastAPI backend on Modal."""
    import subprocess
    # Run the uvicorn command defined in your Dockerfile/compose
    return subprocess.Popen(
        ["uvicorn", "core_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
    )
