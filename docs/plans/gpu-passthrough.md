# Plan: Linux Native GPU Passthrough

## Objectives
1. Swap Ollama image to `uberchuckie/ollama-intel-gpu:latest` for native Linux Intel support.
2. Configure device passthrough using `/dev/dri` instead of WSL2 specific `/dev/dxg`.
3. Enable Intel-specific environment variables (`DEVICE=Arc`, `OLLAMA_INTEL_GPU=true`).

## Implementation Steps
- Update `docker-compose.yml`.
- Restart docker services.
- Verify GPU detection in logs.
