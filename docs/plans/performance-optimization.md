# Plan: Performance Optimization (Browser Persistence & Polars Mapping)

## Background
The current architecture launches/kills Playwright browsers frequently, causing high CPU spikes and `TargetClosedError` crashes. Additionally, `tab_pdf_mapper.py` processes data row-by-row, which is a bottleneck for large racecards.

## Objectives
1. **AdaptiveOddsMonitor**: Refactor to use a single, persistent browser context instead of launching a new one for every poll.
2. **TabPDFMapper**: Refactor to use Polars for vectorized, multi-threaded PDF data mapping.

## Implementation Steps
### 1. Browser Persistence (`adaptive_odds_monitor.py`)
- Modify `monitor_loop` to initialize `playwright` once.
- Create a persistent browser instance and context.
- Update the loop to reuse the `page` instead of re-launching the browser.

### 2. Polars Refactor (`tab_pdf_mapper.py`)
- Read existing parsing logic.
- Replace manual iteration over racecard rows with Polars `DataFrame` construction.
- Vectorize the transformation (e.g., column-based cleaning of names/odds).

## Verification
- **Monitor Logs**: Confirm `Ghost Sync` is continuous without "browser launch" overhead.
- **CPU Metrics**: Observe lower idle CPU usage.
- **Data Integrity**: Verify racecards in `data/` remain structurally sound after Polars mapping.
