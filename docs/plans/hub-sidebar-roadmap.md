# Roadmap: HUD Sidebar Intelligence & Diagnostics

## Vision
Transform the HUD sidebar from a passive log viewer into an active "Command & Control" center that provides immediate decision support, system resilience visibility, and data-enrichment capabilities.

---

## Phase 1: Operational Visibility (The "C2" Center)
*Focus: Turning existing data into instant insights.*

- [ ] **Intelligence Summary Header**:
    - Add a permanent summary bar at the top of the sidebar.
    - Metrics: `Live ROI`, `Today's Edge Captured`, `Active Bets`, `System Status`.
- [ ] **Actionable Sidebar Hooks**:
    - Implement a "Quick Action" row: `[Scan]`, `[Pause Engine]`, `[Force Settle]`.
    - Map these directly to the `core_agent` API endpoints.
- [ ] **Semantic Event Filtering**:
    - Add category toggles for "High-Edge Value Bets" and "Bankroll Risk Events" to instantly filter the operations timeline.

---

## Phase 2: Intelligence & Decision Support (The "Punter's Edge")
*Focus: Visualizing odds movement and probability.*

- [ ] **Real-time Odds Heatmap**:
    - Add sparkline visualization for odds delta over the last 15-30 minutes for active races.
    - Color-code based on value direction (Green = Value increasing, Red = Value eroding).
- [ ] **Edge Probability Curve**:
    - Mini-visualizer showing the gap between Implied Odds vs. Bot Estimated Probability.
    - Allows instant visual betting decision support without deep-diving into the main RaceCard.

---

## Phase 3: Resilience & Learning (The "DevOps" View)
*Focus: Monitoring the Healing Swarm and improving ML data quality.*

- [ ] **Healing Swarm Status Monitor**:
    - Visual status grid for the 7-model cloud swarm.
    - Indicator for which LLM provider (Groq, Gemini, Ollama) is currently handling the load.
- [ ] **System Anomaly Detection**:
    - Histogram display for `Browser Launch/Re-init` frequency.
    - Threshold alerts (e.g., if browser re-inits > 5/min, show red alert).
- [ ] **Betting Journal Annotation**:
    - Add a "Note" button to every logged bet.
    - Allow user to push qualitative feedback (e.g., "Jockey error") back to the `LearningEngine` JSON data store.

---

## Phase 4: Future / Advanced
- [ ] **Voice-over-IP/Telegram integration**:
    - Support for voice command triggers from Telegram within the sidebar.
- [ ] **Automated Portfolio Optimization**:
    - Visualizing Kelly-recommended stakes vs. actual stakes in a sidebar graph.

---

## Implementation Roadmap

| Priority | Feature | Complexity | Impact |
| :--- | :--- | :--- | :--- |
| **High** | Intelligence Summary Header | Low | High |
| **High** | Actionable Quick Actions | Medium | High |
| **Medium** | Odds Heatmap Sparklines | Medium | High |
| **Medium** | Betting Journal Annotations | Medium | Medium |
| **Low** | Healing Swarm Status Monitor | High | Medium |
| **Low** | System Anomaly Histogram | High | Medium |

*Status: Ready for technical breakdown and architectural design.*










  Based on my analysis of LogsView.tsx and the project structure, here are the recommended improvements and new feature additions to
  transform the sidebar into a true "Command & Control" center.

  ---

  1. Operations Improvements (The "Actionable" Sidebar)
   * Contextual Filtering: Instead of just filtering text, add semantic filtering. Let users toggle based on ROI-impactful events (e.g.,
     "High-Edge Value Bets", "Bankroll Stop-Loss Triggered").
   * Aggregated "Intelligence" Summary: Add a top-bar summary above the timeline showing "Live Session Stats":
       * Total Bets Today | Win Rate | Live ROI | Edge Captured. 
       * This provides instant feedback without forcing the user to scroll through logs.
   * One-Click "Re-Scan" Trigger: Add a button in the sidebar specifically for the SCAN operation (currently manual via Docker) to allow
     direct interaction with the agent loop.

  2. Proposed New Features (The "L7 Engineer" View)

  A. The "Race-Card Intelligence" Sidebar
   * Real-time Odds Heatmap: Visualize odds movement for all currently monitored races in the sidebar. Use small sparklines to show the
     delta over the last 15 minutes. This immediately helps identify if a value bet is becoming "worse" or "better."
   * Edge Probability Curve: A small visual graph showing the current "Implied Probability" vs. "Bot Estimate" for active races directly in
     the sidebar list, allowing instant betting decision support without opening the main card.

  B. The "DevOps/Healing" Dashboard (Health Monitoring)
   * Healing Swarm Status: Visual indicator of the 7-model cloud swarm health. If kimi-k2 or gemini-flash are struggling, show which model
     is failing and its recent uptime.
   * Telemetry Anomaly Detection: Instead of raw logs, use a simple histogram in the sidebar to show "Error Rate per Minute." If the browser
     re-init or the scraper spikes, the user gets a visual red alert before the app crashes.

  C. Interactive "Betting Journal" 
   * Quick Annotation: Add a "+" button on every betting log entry to allow the user to add a quick note (e.g., "Jockey fell," "Track bias
     observed") directly to the JSON store for that bet. This will dramatically improve your LearningEngine data quality.

  ---

  Proposed Sidebar Structure Evolution

    1 HUD Sidebar (Current -> Proposed)
    2 ---------------------------------
    3 [System Health Cards] (Keep, but add click-to-debug)
    4 [Quick Actions: Scan, Pause, Settle] (NEW)
    5 ---------------------------------
    6 [Tabs]
    7 1. Intelligence Dashboard (New Sparklines/Heatmaps)
    8 2. Operations Timeline (Existing, optimized)
    9 3. Betting Journal (New - with annotation buttons)
   10 4. Raw Diagnostics (Existing)
   11 ---------------------------------
