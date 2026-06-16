# Plan: Refactor Oddschecker Scraper to Scrapling

## Background
The previous Playwright-based scraper is encountering anti-bot timeouts and stability issues. `Scrapling` offers a more resilient, efficient, and structured alternative.

## Objectives
1. Replace Playwright-based scraper in `core_agent/skills/parsers/oddschecker_scraper.py` with `Scrapling`.
2. Update the target URL to `https://www.oddschecker.com/horse-racing/today` for better data coverage.
3. Keep `AdaptiveOddsMonitor` using Playwright for Betway, as it is already optimized and stable.

## Implementation Steps
1. Update `oddschecker_scraper.py` to use `Scrapling` session and selector logic.
2. Update the scraping logic to use the new URL and CSS selector for odds extraction.
3. Maintain the `AdaptiveOddsMonitor`'s current Playwright implementation for Betway to preserve its stability.

## Verification
- Run a manual test: `python3 -c "..."` to ensure odds are extracted correctly.
- Check logs to ensure background tasks complete without timeouts or `TargetClosedError`.
