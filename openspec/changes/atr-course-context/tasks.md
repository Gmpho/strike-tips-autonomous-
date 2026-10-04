# Tasks: ATR Course Context

## 1. Backend

- [x] 1.1 `ATR_COURSE_MAP` + `normalize_course` + meeting-aware movers/predictor
- [x] 1.2 `atr_enrich.py` backfill + monitor wiring (4 write sites)
- [x] 1.3 TAB dead URL retired; Betway GetDaily international source, loud failures

## 2. OKF

- [x] 2.1 `tracks-uk/`: Newcastle, Southwell, Nottingham, Salisbury + 59-course index
- [x] 2.2 `tracks-ie/`: Bellewstown, Clonmel + 26-course index
- [ ] 2.3 Bundle rebuild + entry check (do with edge deploy)

## 3. HUD

- [x] 3.1 `CourseChip` + `TRACK_INTEL` + `useHorseMeetingIndex`
- [x] 3.2 Predictor cards + modal show course/time/region
- [x] 3.3 Movers venue: chip + cross-ref, "Unknown Venue" eliminated
- [x] 3.4 `npm run build` green

## 4. Tests (no deploy per order)

- [x] 4.1 `test_atr_course_context.py` green (map, backfill, schedule)
- [ ] 4.2 Docker backend suite (needs docker up)
- [ ] 4.3 Deploy backend + edge + HUD on user approval, live-verify both pages
