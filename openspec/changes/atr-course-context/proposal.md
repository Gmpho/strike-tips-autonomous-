# Proposal: ATR Course Context + UK Shelf + TAB Repair

## Why
Predictor cards show no course (users guess from jockeys); 439/574 movers
render "Unknown Venue". ATR predictor/movers pages are UK-only group tables
whose course lives in meeting headers the scraper ignored. The TAB
international schedule URL returns HTML, so discovery silently returned {}.

## What changes
- `attheraces_api.py`: `ATR_COURSE_MAP` + `normalize_course` + meeting-aware
  movers/predictor parsing (predictor gains course/region).
- `atr_enrich.py` (new): snapshot cross-ref backfill at monitor write time.
- `race_schedule.py`: dead TAB URL retired; Betway GetDaily regions/leagues
  source with loud failures.
- OKF: `tracks-uk/` (4 deep-dives + 59-course index), `tracks-ie/` (2 + 26 index).
- HUD: `CourseChip` + `TRACK_INTEL` + `useHorseMeetingIndex`; predictor cards
  + mover venue show course/time/region, never "Unknown Venue".
- No deploys until user approves (explicit order).
