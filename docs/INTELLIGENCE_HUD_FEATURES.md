# 🧠 Strike Tips: Intelligence HUD & Healing Swarm

This document outlines the high-performance monitoring and self-healing infrastructure implemented for the Strike Tips Racing Bot.

## 🚀 Key Features

### 1. Intelligence Vitals (AI Performance HUD)
Shifted from infrastructure-centric monitoring (Docker stats) to **Intelligence-centric telemetry**.
*   **Success Rate Tracking**: Real-time percentage of successful race evaluations per model.
*   **Reasoning Latency**: Tracking the "thought time" (seconds) for each AI instance (`Racing Llama`, `DS Racing`, `Ghost Stealth`).
*   **Request Volume**: Monitoring the throughput of the Intelligence Engine across thousands of data points.
*   **Host Orchestrator Guard**: Secure monitoring of the `strike-bot` process (CPU/RAM) without requiring risky Docker socket mounts.

### 2. The Healing Swarm (Self-Healing Pipeline)
An automated "Immune System" that detects and repairs broken data parsers.
*   **Adaptive Selectors**: Real-time success/failure reporting for Betway and TAB4Racing HTML selectors.
*   **Manual Neural Pulse**: A "Command Center" trigger that allows an admin to force a system-wide intelligence scan.
*   **Agent Activity Feed**: A unified log of internal events and external GitHub Action "Healing" runs.

### 3. Cloud-Hybrid Architecture
Optimized for high-performance reasoning on restricted hardware (8GB RAM).
*   **Local Scanning**: Lightweight monitoring and fast-reads handled by local Ollama (`racing_llama`).
*   **Cloud Healing**: Heavy-duty code fixing and PR generation delegated to GitHub Actions (`gemini-plan-execute.yml`).
*   **Secure API Integration**: Direct GitHub REST API connection for real-time workflow status (no CLI dependencies inside containers).

### 4. Premium HUD Experience
Modern, high-fidelity interface designed for "Zero-Delay" oversight.
*   **Tailwind 4.0 Powered**: Fully updated to the latest `bg-linear-to-r` syntax and layout engine.
*   **Instant-Load Persistence**: State hydration via `localStorage` ensures the dashboard is populated immediately upon refresh (zero-spinner experience).
*   **Framer Motion 3D Layers**: Smooth "Blur-Slide" transitions and micro-animations for a premium feel.

---

## 🛠️ Tech Stack & Integration
*   **Frontend**: Next.js 16+, TypeScript, Tailwind CSS 4.0, Framer Motion.
*   **Backend**: FastAPI (L7 Diagnostics), `psutil` (Bare Metal Telemetry).
*   **AI Orchestration**: Performance Tracker (JSON Persistence).
*   **CI/CD Integration**: GitHub Actions REST API.

---
> [!NOTE]
> **Production Hardening**: The system uses socket-less telemetry, ensuring that the bot container remains isolated and secure while still providing full-stack oversight.
