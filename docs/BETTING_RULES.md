# Betting Rules — Strike Tips Racing Bot

**Effective Date:** June 2026  
**Version:** 1.0  
**Jurisdiction:** South Africa

---

## 1. Purpose

These rules govern the **paper-trading simulation** within Strike Tips Racing Bot. They exist to teach disciplined bankroll management and racing analysis — not to facilitate real betting.

---

## 2. Bankroll Rules (Hard Limits)

| Rule | Value | Enforcement |
|------|-------|-------------|
| Starting bankroll | R1,000 ZAR (virtual) | Configurable via Settings |
| Max bet per race | 5% of current bankroll | Enforced by Bankroll Governor |
| Daily loss limit | 20% of starting bankroll | Auto-stops selections for the day |
| Kelly fraction | 0.5 (Half-Kelly) | Applied to all edge calculations |
| Minimum edge threshold | 5% | Selections below ignored |

**These limits cannot be bypassed in the simulation.**

---

## 3. Selection Criteria

A paper-trade is only recorded when **ALL** conditions meet:

1. **Edge ≥ 5%** — Model probability exceeds implied market probability by ≥ 5%
2. **Data quality ≥ Medium** — Sufficient form/odds data available
3. **Race verified** — Race exists on official card (TAB4Racing)
4. **Odds available** — Live odds from Betway/TAB
5. **Bankroll healthy** — Not in daily loss limit cooldown

---

## 4. Stake Calculation

```
Edge = (Model_Probability × Decimal_Odds) − 1
Raw_Stake = Current_Bankroll × Kelly_Fraction × Edge
Final_Stake = min(Raw_Stake, Current_Bankroll × 0.05)
```

Example: Bankroll R1,200, Edge 8%, Odds 4.0
- Raw = 1,200 × 0.5 × 0.08 = R48
- Cap = 1,200 × 0.05 = R60
- Final = R48

---

## 5. Race Settlement

1. **Auto-settlement** runs post-race via `ResultTracker`
2. **Source:** DuckDuckGo search → official result pages
3. **Matching:** Fuzzy match horse name to winner
4. **Outcomes:** WON / LOST / VOID (non-runner)
5. **Bankroll update:** Immediate on settlement

**VOID rules:** Horse scratched, race abandoned, result unavailable → stake returned

---

## 6. Prohibited in Simulation

- ❌ Overriding max bet % (5%)
- ❌ Ignoring daily loss limit (20%)
- ❌ Betting without verified edge
- ❌ Manual stake adjustments outside Kelly
- ❌ Simulating multiple accounts to circumvent limits

---

## 7. Performance Tracking

Metrics recorded per selection:
- Track, distance, surface, going
- Odds at placement vs. SP
- Edge % at placement
- Result (WON/LOST/VOID)
- P&L impact

Aggregated views:
- ROI by track / distance / odds band
- Strike rate by confidence tier
- Monthly P&L chart

---

## 8. Reset & Archive

- **Manual reset:** Settings → "Reset Bankroll" (sets to R1,000, archives history)
- **Auto-archive:** Monthly snapshot saved to ChromaDB
- **Export:** `/api/betting/history` returns full CSV-compatible JSON

---

## 9. Educational Intent

These rules mirror professional bankroll management. The simulation teaches:
- Discipline (hard limits)
- Value identification (edge threshold)
- Risk sizing (Kelly)
- Record-keeping (full audit trail)

---

## 10. Disclaimer

**This is a paper-trading simulation only.**  
No real money is wagered, won, or lost.  
Rules are for educational demonstration.  
Real betting involves additional risks: bookmaker limits, market efficiency, psychology, liquidity.

See [Disclaimer](/disclaimer) | [Responsible Gambling](/responsible)