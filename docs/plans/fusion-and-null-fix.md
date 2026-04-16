# Plan: Finalizing Odds Fusion & Fixing Null Names

## Background
Currently, some Betway races return `null` names for runners, and strict matching prevents effective Oddschecker price fusion.

## Objectives
1. **Fix Null Names**: Ensure `mapEvent` handles null outcome names by falling back to race event properties or IDs.
2. **Improve Fusion**: Replace exact key-matching with fuzzy matching for races and horses to overcome naming discrepancies.
3. **Enhance Observability**: Add detailed success logs for fusion events.

## Implementation Steps
### 1. Fix Scraper Names (`adaptive_odds_monitor.py`)
- Update `mapEvent` JavaScript to handle nulls: `r.outcomeName || r.name || "Unknown Horse"`.

### 2. Implement Robust Fusion (`adaptive_odds_monitor.py`)
- Implement `match_race` and `match_horse` using `difflib.get_close_matches` with permissive cutoffs.
- Update the merge loop to use these fuzzy matchers.

## Verification
- **Log Inspection**: Confirm `[FUSION] Matched Horse X at Track Y` logs are appearing.
- **Snapshot Inspection**: Ensure no `name: null` entries exist in `market_snapshot_latest.json`.
- **Data Integrity**: Verify runners have valid `odds` and `provider: Oddschecker` tags.
