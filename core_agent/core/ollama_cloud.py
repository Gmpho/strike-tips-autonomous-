"""
Strike Tips — Standalone Ollama Cloud Server

Deploys a minimal Ollama instance on Modal with pre-loaded tiny models.
Separate from the main app to avoid build cache issues and enable
independent model updates.

Usage:
  modal deploy core_agent.core.ollama_cloud
"""

import modal

app = modal.App("strike-tips-ollama-cloud")

OLLAMA_VERSION = "v0.30.8"

image = (
    modal.Image.debian_slim()
    .run_commands(
        "apt-get update && apt-get install -y curl zstd",
        f"curl -fsSLo /tmp/ollama.tar.zst https://github.com/ollama/ollama/releases/download/{OLLAMA_VERSION}/ollama-linux-amd64.tar.zst",
        "zstd -d < /tmp/ollama.tar.zst | tar -xf - -C /usr/local",
        "ollama --version",
        "ollama serve & sleep 5 && "
        "ollama pull embeddinggemma:300m && "
        "ollama pull qwen3.5:0.8b && "
        "ollama pull functiongemma:270m && "
        "echo 'all models pulled'",
    )
)


@app.function(
    image=image,
    cpu=2.0,
    memory=2048,
    min_containers=0,
    scaledown_window=300,
    max_containers=2,
    timeout=3600,
    env={"OLLAMA_HOST": "0.0.0.0:11434"},
)
@modal.web_server(11434, startup_timeout=120)
def ollama():
    """Run Ollama server (non-blocking — Modal manages the process via @web_server)."""
    import subprocess
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
