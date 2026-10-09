# Proposal: Exotics Full Slate

09-Oct-2026 (Fairview/Greyville Friday): 09:30 rescan wiped 05:00 EXA/TRI off
the Hub board (merge replaced whole day/track), PA never generated (no
convention gap-fill), and Greyville R8 leaked fenced JSON to Telegram.

## Scope
- Pool-keyed merge in `_merge_exotic_history` (same pool replaced, missing kept).
- Convention gap-fill for absent pool families + prompt requires ALL pools.
- `send_daily_tips` strips code fences, handles dict insights.
- `core_agent/tests/test_exotics_merge.py` regression tests.
