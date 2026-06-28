---
type: Strategy
title: Kelly Criterion
description: Optimal bet sizing using fractional Kelly, bankroll management, and practical application for SA horse racing
tags: [kelly, bet-sizing, bankroll-management, staking, half-kelly]
timestamp: 2026-06-28T00:00:00Z
---

# Kelly Criterion for Bet Sizing

## The Formula

The Kelly Criterion calculates the optimal fraction of bankroll to wager:

**f\* = (bp - q) / b**

Where:
- f\* = fraction of bankroll to bet
- b = decimal odds - 1 (net odds received)
- p = estimated true win probability
- q = 1 - p (losing probability)

**Simplified form:** f\* = p - (1-p) / (d-1) where d = decimal odds

## Worked Examples

### Example 1: Value at 3/1
- Odds: 4.0 (3/1), b = 3
- Estimated true probability: 30%
- f\* = (3 × 0.30 - 0.70) / 3 = (0.90 - 0.70) / 3 = 0.20 / 3 = **6.67%**

On a R1,000 bankroll: R66.70 bet

### Example 2: Heavy favourite
- Odds: 1.50 (-200), b = 0.5
- Estimated true probability: 60%
- f\* = (0.5 × 0.60 - 0.40) / 0.5 = (0.30 - 0.40) / 0.5 = -0.10/0.5 = **negative — no bet**
- Even though 60% wins, the odds require 66.7% to break even

### Example 3: Small edge on short odds
- Odds: 2.0 (evens), b = 1
- Estimated true probability: 55%
- f\* = (1 × 0.55 - 0.45) / 1 = (0.55 - 0.45) / 1 = **10%**
- On R1,000 bankroll: R100

## Why Fractional Kelly

**Full Kelly** is mathematically optimal for long-term growth but has extreme variance — drawdowns of 30-50% of bankroll are common.

**Half-Kelly** (50% of full Kelly) trades ~25% of growth rate for dramatically reduced variance:
- Full Kelly: R100 bet → Half-Kelly: R50 bet
- Protects against overestimating true probability
- Much smoother bankroll curve
- Most professional bettors use half-Kelly or quarter-Kelly

**Quarter-Kelly** (25%):
- Very low variance
- Suitable for beginners or when confidence in probability estimate is low
- Recommended starting point

## Practical Application for SA Racing

### 1. Combined with MR Analysis

Kelly requires a true probability estimate. In SA racing, your estimate should be built from:
- Recent form and MR trajectory
- Track specialist angle (have they won here before?)
- Going preference match
- Draw advantage/disadvantage
- Class form (have they competed at this level before?)

### 2. Betting Multiple Races

Kelly assumes one independent bet at a time. When betting multiple races on the same card:
- **Conservative approach:** Apply Kelly to each separately, divide total across bets
- **Simplest approach:** Use same fraction (e.g., 1% of bankroll = 1 unit) for each bet

### 3. Bankroll Updates

Kelly works best when you recalculate after every bet:
- After win: bankroll grows → stakes increase automatically
- After loss: bankroll shrinks → stakes decrease automatically
- This is the built-in protection mechanism

### 4. Maximum Stake Limits

Even with half-Kelly, cap maximum stake:
- Never exceed 5% of bankroll on a single bet (hard cap)
- Fractional Kelly rarely produces >5% anyway, but the cap prevents disaster
- If Kelly suggests >5%, it means either the edge is enormous or your probability estimate is wrong

## Circuit Breakers

If bankroll drops by:
- **20%:** Reduce all stakes by 50% for 50 bets
- **33%:** Stop betting entirely for 7 days. Review process.
- **50%:** Bankroll halved. Return to minimum stakes with quarter-Kelly.

## Common Mistakes

1. **Overestimating probability** — The most common error. Be conservative with your estimates.
2. **Chasing losses** — Never increase stake after a loss. Kelly already adjusts for this.
3. **Betting too many races** — Better to skip 80% of races and bet only when there's a clear edge.
4. **Ignoring the takeout** — SA racing has bookmaker margins. Make sure your estimate accounts for this.
5. **Full Kelly on low sample** — With fewer than 500 bets, variance can be extreme. Use fractional Kelly.
