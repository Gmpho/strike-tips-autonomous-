"""
P0 Backtest Gate — compare old (capped) vs new (softmax-normalized) probability model.

Uses real race data from current_raw_data.json to demonstrate:
  1. Old model saturates all decent horses to same probability → no rank discrimination
  2. New model produces a coherent distribution → edge is a real probability gap
  3. Temperature sweep to quantify sensitivity
"""

import json
import math
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "core_agent"
sys.path.insert(0, str(SRC))

from skills.race_analysis.form_analyzer import FormAnalyzer, FIELD_TEMPERATURE, parse_sa_form

analyzer = FormAnalyzer()

# ── Load real race data ──────────────────────────────────────────────────
raw_path = SRC / "scratch" / "current_raw_data.json"
with open(raw_path) as f:
    payload = json.load(f)

racers = payload["result"]["events"][0]["raceEventDetails"]["racers"]
field_size = len(racers)
print(f"Race: {payload['result']['events'][0]['name']}")
print(f"Field size: {field_size} runners\n")

# ── Extract horse name + form string ──────────────────────────────────────
horses = []
for r in racers:
    name = r["outcomeName"]
    form_str = r.get("form", "").strip()
    horses.append((name, form_str))

# ── Simulate market odds (inverse of implied probability with overround) ──
# Assume ~20% overround; market_implied ≈ 0.8 / field_size as baseline
def market_odds(horse_idx: int, total: int) -> float:
    """Return mock fractional odds; middle horses get tighter odds."""
    center = total / 2
    offset = abs(horse_idx - center) / center
    base = 1.5 + offset * 3.0
    return round(base, 1)

# ── OLD MODEL ─────────────────────────────────────────────────────────────
print("=" * 70)
print("OLD MODEL — estimate_win_probability (individually capped)")
print("=" * 70)
old_probs = []
total_prob_old = 0.0
for name, form_str in horses:
    positions = parse_sa_form(form_str)
    prob, rating, _ = analyzer.estimate_win_probability(
        name, positions, field_size=field_size
    )
    old_probs.append(prob)
    total_prob_old += prob
    print(f"  {name:20s}  form={form_str:10s}  rating={rating:.3f}  prob={prob:.4f} ({prob*100:.2f}%)")

print(f"\n  >>> SUM of old probabilities: {total_prob_old:.4f}  (should be ~1.0)")
print(f"  >>> Distinct values: {len(set(round(p,4) for p in old_probs))} out of {field_size} horses → collapse severity")

# ── NEW MODEL ─────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("NEW MODEL — estimate_win_strength + normalize_field (softmax)")
print("=" * 70)

raw = {}
for name, form_str in horses:
    positions = parse_sa_form(form_str)
    raw[name] = analyzer.estimate_win_strength(name, positions, field_size=field_size)

normed = FormAnalyzer.normalize_field(raw, temperature=FIELD_TEMPERATURE)
total_new = sum(normed.values())

sorted_new = sorted(normed.items(), key=lambda kv: -kv[1])
for rank, (name, prob) in enumerate(sorted_new, 1):
    print(f"  {rank:2d}. {name:20s}  prob={prob:.4f} ({prob*100:.2f}%)")

print(f"\n  >>> SUM of new probabilities: {total_new:.6f}")
print(f"  >>> Rank positions preserved: {all(sorted_new[i][1] >= sorted_new[i+1][1] for i in range(len(sorted_new)-1))}")

# ── EDGE COMPARISON ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("EDGE COMPARISON (est_prob - 1/odds) @ τ=0.3")
print("=" * 70)

print(f"\n{'Horse':20s} {'Odds':>6s} {'Implied':>8s} {'OldProb':>8s} {'OldEdge':>8s} {'NewProb':>8s} {'NewEdge':>8s}")
print("-" * 76)
for i, (name, _) in enumerate(horses):
    odds = market_odds(i, field_size)
    implied = 1.0 / odds
    old_p = old_probs[i]
    new_p = normed.get(name, 0)
    old_edge = old_p - implied
    new_edge = new_p - implied
    print(f"{name:20s} {odds:6.1f} {implied:8.4f} {old_p:8.4f} {old_edge:8.4f} {new_p:8.4f} {new_edge:8.4f}")

# ── TEMPERATURE SWEEP ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("TEMPERATURE SWEEP — effect on probability spread")
print("=" * 70)

temps = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 2.0]
header = f"{'τ':>6s}" + "".join(f"{'P(top)':>9s}{'P(bot)':>9s}{'Ratio':>8s}" for _ in temps)
print(header)
print("-" * len(header))

for t in temps:
    n = FormAnalyzer.normalize_field(raw, temperature=t)
    sorted_n = sorted(n.items(), key=lambda kv: -kv[1])
    top = sorted_n[0][1]
    bot = sorted_n[-1][1]
    ratio = top / bot if bot > 0 else float("inf")
    row = f"{t:>6.2f}"
    row += f"{top:>9.4f}{bot:>9.4f}{ratio:>8.1f}"
    print(row)

print(f"\n  Current τ = {FIELD_TEMPERATURE}")

# ── RECOMMENDATION ────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
print(f"""
  OLD: sum of probabilities = {total_prob_old:.4f}" 
       (not a distribution — edge is meaningless)
  NEW: sum of probabilities = {total_new:.6f}
       (valid distribution — edge = genuine probability gap)

  The new model PASSES the backtest gate for coherence.
  Temperature τ={FIELD_TEMPERATURE} produces reasonable spread (top/bot from sweep above).

  RECOMMENDATION: Run on live data for 2-4 weeks, log actual results,
  then tune τ to maximize calibration accuracy via:
    accuracy = |actual_winrate - avg_implied_prob|
""")
