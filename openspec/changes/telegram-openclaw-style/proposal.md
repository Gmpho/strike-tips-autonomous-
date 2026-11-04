# Proposal: OpenClaw-Style Telegram (SOUL + Tables + Guard Fix)

## Why
Telegram answers parrot the snapshot on any turn containing generic nouns
("bet", "odds", "race"), never route to web search (no search intent
exists), and render data as unstructured prose — while the HUD shows rich
columnar tables. The `wants_live_card` over-triggering is the months-old
root bug from before the HUD existed.

## What changes
- New `core_agent/agent/SOUL.md` (trackside pundit voice), loaded into the
  Telegram system prompt only.
- `wants_live_card`: explicit search-intent negatives suppress the card and
  force `search_racing_data`; drop `bet`, `stake`, `edge` from `_CARD_NOUNS`.
- New `markdown_table_to_pre()` in `telegram_format.py`, wired into the
  webhook `_send` path before chunking.
- System-prompt table rule: compact (Horse|Odds|Edge) default, full
  (draw/gear/days/pedigree) on "full"; preference persisted in session.
- Execute-position prompt enriched from the Runner type (draw, gear,
  daysSinceRun, pedigree already exist).

## Impact
- Telegram-only behavior change. HUD untouched. No money paths touched.
- Model-facing tool list unchanged.
