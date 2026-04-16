# Plan: Integrate Oddschecker Odds Scraper

## Background
Betway's API frequently locks prices or obfuscates data. Oddschecker provides a standardized, clean source for horse racing odds that can act as a reliable alternative or confirmation source.

## Objectives
1. Create a dedicated Oddschecker scraper skill in `core_agent/skills/parsers/oddschecker_scraper.py`.
2. Ensure it produces clean, standardized JSON output similar to our existing `market_snapshot_latest.json`.
3. Integrate this into `core_agent/core/adaptive_odds_monitor.py` to allow multi-source odds polling.

## Implementation Steps
1. **Research**: Investigate the structure of Oddschecker's horse racing page (via browser tools) to identify selectors or API endpoints.
2. **Draft Scraper**: Create a new class `OddscheckerScraper` that uses `playwright` or `httpx` to fetch and parse odds.
3. **Integration**: Modify `AdaptiveOddsMonitor` to run both scrapers (or switch if one fails).
4. **Verification**: Run a test scan and confirm data integrity.

## Alternatives Considered
- **Direct Site Scraping**: High maintenance due to anti-bot protections.
- **Third-party API**: Costly and might not cover local SA tracks as well as domestic sources.
- **Oddschecker**: Recommended as it offers a clean "aggregate" view.

## Verification
- Confirm that `odds_source` in the JSON output correctly identifies the data provider.
- Validate that the data structure is compatible with the `AdaptiveOddsMonitor` parsing logic.
