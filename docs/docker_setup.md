# Docker Migration & "Turbo Build" Guide

This document summarizes the migration of the Strike Tips backend to a containerized environment with a stable bridge to Windows-hosted Ollama models.

## 🌉 The Windows-Linux Bridge
To save disk space (~5GB), we configured the Linux Docker container to talk to the **Windows** Ollama instance.

1.  **Windows Side:**
    *   Set `OLLAMA_HOST=0.0.0.0` to allow external connections.
    *   Added a Firewall rule: `New-NetFirewallRule -DisplayName "Ollama for WSL" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 11434`.
2.  **Bot Side (.env):**
    *   Set `OLLAMA_HOST=http://host.docker.internal:11434`.
3.  **Networking:**
    *   Used `extra_hosts: ["host.docker.internal:host-gateway"]` in `docker-compose.yml` to resolve the Windows host.

## 🚀 "Turbo Build" Optimizations
We reduced the Docker build time from **1 hour** to **~25 minutes** (and subsequent changes to seconds) by:
*   **Layered Installation:** Installing heavy libraries (`chromadb`, `playwright`, `pydantic-ai`) in their own Docker layers before copying code.
*   **Binary Preference:** Used `--prefer-binary` to avoid slow compilations.
*   **Version Pinning:** Fixed `agent-framework==1.0.0rc4` and `pydantic-ai==1.73.0` to prevent dependency resolution loops.

## 🛠️ Critical Bug Fixes
*   **NumPy 2.0 Incompatibility:** Fixed an `AttributeError: np.float_` by pinning `numpy<2.0` in both the `Dockerfile` and `requirements.txt`. This is required for ChromaDB/ONNX stability.
*   **Port Binding:** Updated the startup command to `uvicorn api:app --host 0.0.0.0 --port 8000` to ensure the API is reachable from your browser.

## 🕹️ Operational Commands
Always run these from the `strike-tips` directory:

| Action | Command |
| :--- | :--- |
| **Start Bot** | `docker-compose up -d` |
| **Stop Bot** | `docker-compose down` |
| **View Logs** | `docker logs -f strike-tips` |
| **Restart** | `docker-compose restart strike-tips` |
| **Update Code** | `docker-compose up -d --build` (Takes ~2s) |

---
*Status: Migrated & Verified - March 28, 2026*
