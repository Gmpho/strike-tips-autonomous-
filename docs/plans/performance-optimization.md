# Plan: Performance Optimization (Browser Persistence & Polars Mapping)

## Background
The current architecture launches/kills Playwright browsers frequently, causing high CPU spikes and `TargetClosedError` crashes. Additionally, `tab_pdf_mapper.py` processes data row-by-row, which is a bottleneck for large racecards.

## Objectives
1. **AdaptiveOddsMonitor**: Refactor to use a single, persistent browser context instead of launching a new one for every poll.
2. **TabPDFMapper**: Refactor to use Polars for vectorized, multi-threaded PDF data mapping.

## Implementation Steps
### 1. Browser Persistence & Error-Recovery (`adaptive_odds_monitor.py`)
- Modify `monitor_loop` to initialize `playwright` once.
- Create a persistent browser instance and context.
- Update the loop to reuse the `page` instead of re-launching the browser.
- **Error-Recovery Protocols**:
    - **Health Checks**: Every N polls, verify session with `page.evaluate("1+1")`.
    - **Lazy Re-init**: If `page` or `context` is stale/disconnected, tear down instance and perform lazy re-initialization.
    - **Navigation Watchdog**: If page load hangs >30s, force-reset browser context.
    - **Exponential Backoff**: Implement retry logic for re-initialization to prevent thrashing.

### 2. Polars Refactor (`tab_pdf_mapper.py`)
- Replace manual iteration over racecard rows with Polars `DataFrame` construction.
- Vectorize the transformation (e.g., column-based cleaning of names/odds).

## Verification
- **Monitor Logs**: Confirm `Ghost Sync` is continuous without "browser launch" overhead.
- **CPU Metrics**: Observe lower idle CPU usage.
- **Data Integrity**: Verify racecards in `data/` remain structurally sound after Polars mapping.
- **Resilience Test**: Simulate browser process termination and verify auto-recovery.





Refined Plan: Performance Optimization (Browser Persistence & Polars Mapping)

  1. Objectives
   * Zero-Jank Odds Monitoring: Reduce CPU spikes and prevent TargetClosedError by maintaining a persistent browser session.
   * Vectorized Data Processing: Eliminate row-by-row bottlenecks in PDF mapping using Polars.

  2. Implementation Steps

  Task 1: Browser Persistence (core_agent/skills/monitor/adaptive_odds_monitor.py)
   * Singleton Browser Pattern: Refactor AdaptiveOddsMonitor to hold browser and context as class-level state.
   * Health-Check Loop: Add a lightweight page.evaluate("1+1") check at the start of every poll; if it fails, auto-reinitialize the browser.
   * Graceful Teardown: Add an __del__ or shutdown method to ensure the browser context is closed properly when the container stops.

  Task 2: Polars Refactor (core_agent/skills/parsers/tab_pdf_mapper.py)
   * Vectorized Mapping: Replace the current iterative list-of-dicts approach with a construction of a polars.DataFrame.
   * Transformation Pipeline: Use Polars' expression language (pl.col(...).str.strip().cast(...)) to clean odds and names in a single
     vectorized pass.
   * Concurrency: Ensure mapping utilizes all available CPU cores (Polars default).

  3. Verification & Performance Benchmarking

  ┌─────────────────┬─────────────────────────────┬─────────────────────────────────────────────────────────────────────────┐
  │ Metric          │ Verification Method         │ Success Criteria                                                        │
  ├─────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ CPU Overhead    │ docker stats                │ < 15% CPU usage while idle.                                             │
  │ Stability       │ docker logs                 │ Zero TargetClosedError or browser launch logs in 1-hour window.         │
  │ Processing Time │ Timing logs in TabPDFMapper │ > 40% reduction in processing time for full racecards.                  │
  │ Data Integrity  │ Comparison test             │ Output JSON structure identical to pre-refactor (unit test validation). │
  └─────────────────┴─────────────────────────────┴─────────────────────────────────────────────────────────────────────────┘
  ---




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
