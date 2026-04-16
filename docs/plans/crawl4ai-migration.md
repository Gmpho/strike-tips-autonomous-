# Plan: Refactor Oddschecker Scraper to Crawl4AI

## Background
The previous Playwright-based scraper is encountering anti-bot timeouts and stability issues. `Crawl4AI` offers a more resilient, efficient, and structured alternative.

## Objectives
1. Replace Playwright-based scraper in `core_agent/skills/parsers/oddschecker_scraper.py` with `Crawl4AI`.
2. Update the target URL to `https://www.oddschecker.com/horse-racing/today` for better data coverage.
3. Keep `AdaptiveOddsMonitor` using Playwright for Betway, as it is already optimized and stable.

## Implementation Steps
1. Update `oddschecker_scraper.py` to use `AsyncWebCrawler` from `crawl4ai`.
2. Update the scraping logic to use the new URL and CSS selector.
3. Maintain the `AdaptiveOddsMonitor`'s current Playwright implementation for Betway to preserve its stability.

## Verification
- Run a manual test: `python3 -c "..."` to ensure odds are extracted.
- Check logs to ensure background tasks complete without timeouts or `TargetClosedError`.
