# Proposal: Europe Wave (TAB Manifest + 12:30 Cron)

## Why
SA returns Thursday; UK/IRE race daily with TAB Computaform PDFs available,
but discovery relied on a dead JSON URL and scans had no region path.

## What changes
- `tab_content.py` (new): date-parameterized TAB manifest per tag group —
  the front door for all non-SA cards. Loud failures, never silent {}.
- `race_schedule.py`: dead TAB URL retired (kept as documented warning);
  Betway GetDaily international source.
- `strike_tips.py`: `run_region_scan(regions)` — manifest-only meetings,
  digest-only (no auto-bets/alerts/memory writes). CLI `scan --region UK,IRE`.
- `modal_app.py`: `europe_scan` 12:30 SAST (4th of 5 crons).
- `telegram_bot.py`: `send_daily_tips` title param (Europe Intelligence Report).
- No deploy until approved.
