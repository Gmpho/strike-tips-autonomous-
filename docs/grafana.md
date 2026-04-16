 Grafana Integration Plan: Strike Tips Core

   1. Metric Exporter (Prometheus):
       * Bankroll Management: Instrument `skills/bankroll_manager/governor.py` to expose `current_bankroll`, `drawdown_percent`, and `total_profit_loss` as Prometheus gauges which update during `record_bet` and `settle_bet`.
       * Betting Performance: Expose probability edges and Kelly-Criterion stakes from `skills/race_analysis/analyzer.py` via `prometheus_client`.
       * FastAPI Endpoint: Expose a `/metrics` endpoint via ASGI app in `api.py`.
       * Pushgateway: Since `strike_tips.py scan` is a short-lived script, implement a Prometheus Pushgateway upload at the end of the script track loop.

   2. Log Aggregation (Loki):
       * Use `python-logging-loki` to stream logs continuously to Grafana Cloud.
       * Route stdout prints into traditional logging levels (`INFO`, `WARNING`, `ERROR`) to categorize issues effectively.
       * Log edge threshold misses in `analyzer.py` to monitor how often the bot refuses to bet.

   3. Trace Analysis (Tempo):
       * Use `opentelemetry-instrumentation-fastapi` for tracing inbound API requests.
       * Instrument `strike_tips.py`'s `scrape_and_analyze_track` with spans measuring Web Scraping length vs AI prompt inference length (`_call_kimi_parallel`).

  ---

  Implementation Roadmap


  ┌─────────────────┬─────────────────────────┬─────────────────┐
  │ Phase           │ Task                    │ Deliverable     │
  ├─────────────────┼─────────────────────────┼─────────────────┤
  │ 1.              │ Integrate               │ metrics.py      │
  │ Instrumentation │ Prometheus/Loki clients │ service.        │
  │                 │ into Python backend.    │                 │
  │ 2. Dashboarding │ Build the "Strike Tips  │ Bankroll & Bet  │
  │                 │ Dashboard" in Grafana   │ history charts. │
  │                 │ folder dfgscya4yvojka.  │                 │
  │ 3. Alerting     │ Set up "Emergency Stop" │ Slack/Telegram  │
  │                 │ alerts (e.g., 20% loss  │ alert.          │
  │                 │ limit reached).         │                 │
  └─────────────────┴─────────────────────────┴─────────────────┘

  ---

  Suggested docs/grafana.md Structure

    1 # Grafana Documentation: Strike Tips Core
    2
    3 ## Overview
    4 This document outlines the monitoring and observability
      architecture for the Strike Tips AI betting system.
    5
    6 ## Data Sources
    7 - **Metrics (Prometheus)**: System health, bankroll status, and
      betting performance.
    8 - **Logs (Loki)**: Detailed analysis logs and system errors.
    9 - **Traces (Tempo)**: Performance bottlenecks during race
      scanning.
   10
   11 ## Folder: Strike Tips Core (UID: dfgscya4yvojka)
   12 This folder contains the primary operational dashboards.
   13
   14 ## Operational Alerts
   15 - **Loss Threshold**: Alert triggered when >15% of daily
      bankroll is lost.
   16 - **Error Rate**: Alert triggered on repeated scan failures.