# Strike Tips Production & Growth Plan 2026

## 1. Executive Summary
Strike Tips is transitioning from an AI analytics prototype to a market-leading betting intelligence platform. Our competitive edge is combining rigorous probability edge analysis with a disciplined "God Mode" bankroll governance framework.

## 2. Product Strategy (Monetization)
We are adopting a tiered revenue model to drive rapid user adoption followed by high-LTV retention.

| Feature | Free Starter | Premium (R300/mo) |
| :--- | :--- | :--- |
| **Race Discovery** | Delayed (15m+) | Real-time |
| **Probability Edge Analysis** | Standard | Deep Edge Analysis |
| **Bankroll Governor** | Basic | Advanced |
| **Alerting** | Public Channels | Private Alerts (Telegram) |
| **ROI Analytics** | Aggregated | Personal/Detailed |

## 3. SEO/AEO Content Strategy (Growth Pillars)
We will focus on **AEO (Answer Engine Optimization)** to ensure Strike Tips is cited as the authority by AI search engines.

### Content Pillars & Calendar
*   **Pillar 1: Data-Driven Betting Education** (Focus: AEO)
    *   *Focus:* Explain the mathematics of edge betting.
    *   *Sample:* "How Probability-Edge Betting Beats Traditional Tipsters (2026 Analysis)."
*   **Pillar 2: Technical Track Deep-Dives** (Focus: Organic Search/SEO)
    *   *Focus:* High-utility statistics for SA tracks.
    *   *Sample:* "Turffontein Track Bias: A Statistical Analysis for Value Punters."
*   **Pillar 3: AI Assistant Experience** (Focus: Feature Marketing)
    *   *Focus:* Showcasing the bot’s capabilities as a peer-analyst.
    *   *Sample:* "How Strike Tips AI Analyzes Biometric & Surface Data in Seconds."

---

## 4. Technical Implementation Roadmap

| Priority | Plan / Task | Objective |
| :--- | :--- | :--- |
| 1 | performance-optimization.md | Browser persistence + Polars mapping. |
| 2 | scrapling-migration.md | Stable odds scraping with Scrapling. |
| **3** | `fusion-and-null-fix.md` | Fix name fusion and null values. |
| **4** | `smart-routing.md` | AI-based intent routing. |
| **5** | `gpu-passthrough.md` | Linux native GPU acceleration. |

*Phase 2 (Months 3-6): UK/International Data Integration*

---

## 5. KPIs & Success Metrics
1.  **Conversion**: Convert 5% of free users to R300/mo premium tier.
2.  **Retention**: Maintain < 10% churn on premium subscriptions via value-demonstration emails.
3.  **AEO Authority**: Achieve top-3 ranking in AI answer engines for "SA horse racing value betting."
4.  **Operational Efficiency**: Maintain 99.9% uptime on the OddsMonitor scraper.



🏇 Strike Tips Production & Growth Plan (Draft 2026)

  1. Market & Competitive Strategy
  Market Intelligence Summary: The SA market is "Winner-Take-All" for high-intent punters using data-free, mobile-first analytics.
  Competitors like Betshezi (Hoory AI) and Predictify have set the standard for high-speed, conversational AI betting advice. 

  Our Edge:
   * Operational Transparency: Unlike black-box ML models, our probability edge analysis explains the "why" behind every value tip.
   * Strict Bankroll Governance: We are not just giving tips; we are providing a structured professional betting framework (Half-Kelly +
     loss limits).
   * Agile Infrastructure: Our L7-optimized swarm architecture allows us to add new tracks/regions (like the UK) faster than legacy
     monolithic bookmakers.

  ---

  2. Monetization (Free vs. Premium)

  ┌────────────────────────┬─────────────────┬─────────────────────────────────┐
  │ Feature                │ Free Starter    │ Premium (R300/mo)               │
  ├────────────────────────┼─────────────────┼─────────────────────────────────┤
  │ Race Discovery         │ Delayed (15m+)  │ Real-time                       │
  │ Probability Analysis   │ Standard        │ Deep Edge Analysis              │
  │ Bankroll Governor      │ Basic           │ Advanced (Full Portfolio Logic) │
  │ Alerting               │ Public Channels │ Private Alerts (Telegram)       │
  │ Analytics/ROI Tracking │ Aggregated      │ Personal/Detailed               │
  └────────────────────────┴─────────────────┴─────────────────────────────────┘
  ---

  3. Growth & SEO Strategy (Engineering-First)
  To compete with established giants, we will utilize an "AI-First SEO" (AEO) approach.

   * Content Pillars (SEO):
       * Value Betting Logic: Content explaining the math of probability edge.
       * Track-Specific Intelligence: Turffontein, Greyville, and Kenilworth statistical deep-dives.
       * Educational AI: "How our AI analyzes track surface and jockey form."
   * AEO (Answer Engine Optimization): Ensure our answers are structured for immediate ingestion by AI search (Perplexity, Gemini, ChatGPT)
     as the "authority" on SA horse racing statistics.
   * Content Loop: Use the ResultTracker and LearningEngine findings to generate weekly "Why the AI was right/wrong" content reports
     automatically.

  ---

  4. Technical Roadmap & UK Expansion

  Immediate (SA Production Stability)
   * Infrastructure Hardening: Upgrade the docker-compose to a high-availability setup with auto-healing, monitoring (Grafana), and incident
     management (Grafana Incident).
   * Real-time HUD: Finish the "Agent Dashboard" for monitoring AI activity.

  UK Expansion (Months 3-6)
   * Localization Layer: 
       * Implement timezone/currency mapping in the ProviderRouter.
       * Register UK data feeds (e.g., Sporting Life/Racing Post).
   * Compliance Bridge: Develop an automated compliance tool to filter betting data against UKGC (UK Gambling Commission) standards.

  ---

  5. Execution Roadmap

  ┌───────────┬──────────────────────┬────────────────────────────────────────────────────┐
  │ Phase     │ Focus                │ Deliverables                                       │
  ├───────────┼──────────────────────┼────────────────────────────────────────────────────┤
  │ Alpha     │ Production Hardening │ Grafana Dashboards, 99.9% uptime for scrapers.     │
  │ Beta      │ Premium Feature Gate │ Stripe/Paystack integration (Free vs Premium).     │
  │ Go-Live   │ Market Penetration   │ SEO Content Launch, AEO Optimization.              │
  │ Expansion │ UK Integration       │ Timezone-aware engine, UK data source integration. │
  └───────────┴──────────────────────┴────────────────────────────────────────────────────┘
  












Summary of Updated Plan:
   1. Browser Persistence & Error-Recovery:
       * Health Checks: Periodic verification of the browser session.
       * Lazy Re-init: Automatic teardown and clean restart upon session failure.
       * Navigation Watchdog: Force-reset for hung page loads (>30s).
       * Exponential Backoff: Prevents thrashing during outages.
   2. Polars Refactor: Vectorized mapping of racecard data.

  All plans (STRIKE_TIPS_MASTER_PLAN_2026.md, scrapling-migration.md, and performance-optimization.md) are now updated and ready for review
  in @docs/plans/.

*Last Updated: 2026-06-14*
