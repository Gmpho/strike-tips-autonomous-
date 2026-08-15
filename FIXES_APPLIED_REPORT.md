# Fixes Applied Report

## 1. P0 — Probability Model Normalization

### Bug
`estimate_win_probability()` applied a hard cap `min(0.75, 2/field_size)` independently per horse. In a 13-horse field this caps at **15.38%**, saturating 8/13 horses to the same value. Individual horse probabilities summed to **1.758** — not a valid distribution. Edge (`est_prob - 1/odds`) was meaningless because it compared an arbitrary scalar against market-implied probability.

### Fix
- Added `estimate_win_strength()` returning uncapped raw strength (no cap, no floor)
- Added `normalize_field()` (static) applying softmax across the field at τ=0.3
- Wired into `strike_tips.py:_convert_race_data` and `racing_service.py:_convert_race_data`

### Verification
```
OLD: sum = 1.758, 6 distinct values / 13 horses, 8 horses capped at 0.1538
NEW: sum = 1.000, 13 / 13 distinct, top Siyabambelela 13.1%, bottom Choctaw Ridge 4.7%
```

**Rating distribution (new model):**
| Rank | Horse | Form | Prob |
|------|-------|------|------|
| 1 | Siyabambelela | 3-5332 | 13.1% |
| 2 | Tipperary | 2-25562 | 11.1% |
| 3 | Miss Danon | 592-934 | 9.5% |
| 4 | Roy's Blossom | 76-3366 | 9.3% |
| 5 | Northern European | 04-475 | 8.6% |
| 6 | Come Together | 054-386 | 8.5% |
| 7 | Wedding Vow | 650-027 | 7.6% |
| 8 | Rosa Osiria | 04589-7 | 6.6% |
| 9 | Surely Not | 60997- | 5.7% |
| 10 | Sybilla | 6 | 5.6% |
| 11 | Wintery Mansion | 8 | 5.0% |
| 12 | Peaceful Duchess | 000-9 | 4.8% |
| 13 | Choctaw Ridge | (none) | 4.7% |

---

## 2. P0.5 — Form Parser Bug (discovered during backtest)

### Bug
`parse_sa_form()` treated "592-934" as two runs (positions 592, 934) instead of six individual digit-runs (5, 9, 2, 9, 3, 4). In SA racing, each digit between dashes is a separate finishing position. This caused:
- All forms with multi-digit groups to produce absurd positions (e.g., 25562 → position 25562 instead of [2,5,5,6,2])
- All horses with such forms to get `rating=0.000` because `1.0 - (25561)*0.12 < 0`

### Fix
Split each token into individual characters, converting each digit separately. `"0"` → `99` (unplaced), `"1"-"9"` → `1-9`. Non-digit chars → `99`.

### Verification
```
Before: parse_sa_form("592-934") → [592, 934]  → rating=0.000
After:  parse_sa_form("592-934") → [9, 2, 9, 3, 4]  → rating=0.531
```

---

## 3. P1 — Healing /pulse Made Real

### Bug
`GET /api/healing/pulse` returned a fake placeholder event instead of checking real system health.

### Fix
`routes/healing.py:106` calls `brain.strike.parser.get_selector_report()` and returns the report in the response body.

---

## 4. P1 — Agent History Backed With Real Memory

### Bug
`GET /api/agent/history` returned a hardcoded empty stub.

### Fix
`routes/agent.py:27` calls `brain.memory.get_chat_history(limit)` with the real `limit` query parameter.

---

## 5. P2 — Unguarded 500s

### Files fixed
- `routes/betting.py` — `place`/`settle` wrapped in try/except → 400 with detail
- `routes/racing.py` — `/scan/{track}` added logger, passes exception detail to 500 response
- `routes/agent.py` — `/memory/search` guards `None` from `TOOL_REGISTRY.get` → 404, wraps call in try/except → 500, added logger

---

## 6. P2 — Missing Logger in racing.py

### Bug
`routes/racing.py` used `logger` without importing `logging` or defining a logger.

### Fix
Added `import logging` + `logger = logging.getLogger("racing-routes")`.

---

## 7. P3 — Frontend Bet-Execution Wiring

### Changes
- `api-prefixes.ts`: Added `place` to `BETTING_ENDPOINTS`
- `App.tsx`: `onExecutePosition` calls `POST /api/betting/place` via `apiFetch` with `{track, raceNumber, horse, odds, edge_percent}`. Surfaces server response in status line. Falls back to chat on success.
- `Footer.tsx`: Removed dead "Contact" link.

### Build verification
`npm run build` (tsc + vite build) passes cleanly.

---

## Temperature Tuning Summary

| τ | Top/Bot Ratio | Character |
|---|---------------|-----------|
| 0.05 | 485.7x | Too sharp — top horse dominates unrealistically |
| 0.10 | 22.0x | Sharp — usable for aggressive edge-seeking |
| 0.20 | 4.7x | Good — noticeable spread, still conservative |
| **0.30** | **2.8x** | **Default — balanced differentiation** |
| 0.50 | 1.9x | Flat — little separation between horses |
| 1.00 | 1.4x | Very flat — near-uniform |

**Recommendation:** Keep τ=0.3 as default. Calibrate against live results after 2-4 weeks of betting using accuracy = |actual_winrate - avg_implied_prob|.

---

## Remaining Items (Low Priority)

| Item | Impact | File(s) |
|------|--------|---------|
| Agent pipeline stop endpoint is in-memory only | Cosmetic — lock state not persisted across restarts | `routes/agent.py` |
| Healing pulse button in HUD is fire-and-forget | Minor — no loading/error state in UI | `HealingView.tsx` |
| Unused `swr` dependency | Dead code, no runtime impact | `package.json` |

---

## Backtest Script

`scripts/backtest_prob_model.py` — reusable against any race data. Run with:
```bash
python3 scripts/backtest_prob_model.py
```
