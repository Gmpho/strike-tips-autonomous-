# Grafana Observability Status: Strike Tips Racing Bot

This document outlines the current state of our Grafana observability stack, detailing how the bot's internal logic is being monitored in real-time.

## 📊 Current Stack
- **Prometheus**: Scraping API metrics (latency, request counts) from the Strike Tips backend.
- **Loki**: Processing real-time logs via the `strike_tips_logs` API source, now featuring standardized `[L7-ACTION]` markers.
- **Grafana Cloud**: Centralized dashboards for infrastructure and application health.

## 🟢 Monitoring Markers
To ensure the AI Agent's decision-making is observable, we've implemented these primary markers:

| Marker | Description | Key Insight |
| :--- | :--- | :--- |
| `[L7-INTENT]` | Detected User Intent | Confirms if the AI understood the user's request correctly. |
| `[L7-ACTION: SCAN]` | Track Analysis Trigger | Logs when the bot starts scraping and analyzing a specific track. |
| `[L7-ACTION: BET]` | Value Bet Identification | Highlights when the engine finds a high-edge betting opportunity. |
| `[L7-ACTION: INFO]` | Status/Bankroll Query | Logs general information requests and bankroll status checks. |

## ✅ Recent Enhancements
- **Standardized Logging**: Unified `[L7]` prefixes allow for easy filtering in Loki logs.
- **Encoding Fix**: Implemented `PYTHONIOENCODING="utf-8"` across processes to ensure characters (like jockey names/odds symbols) render correctly in Grafana.
- **Observability Dashboard Check**: Verified that all four core modules (`prometheus.scrape`, `prometheus.remote_write`, `loki.source.api`, and `loki.write`) are successfully running and pushing data.

## ⚠️ Known Status
- **Scan Errors**: Fixed the `charmap` codec error that previously plagued Windows terminals.
- **L7 Orchestrator**: Logic clean-up performed in `ai_pydantic.py` to prevent `UnboundLocalErrors` during action execution.

---
*Last Updated: 2026-03-23 | Senior AI DevOps Compliance*
