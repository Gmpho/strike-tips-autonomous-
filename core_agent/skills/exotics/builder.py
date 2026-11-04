from typing import Dict, List, Tuple, Any

# Canonical SA pool codes (as extracted from Computaform leg_info) → leg counts.
# BI1/BI2 = Bipot, JP1/JP2/JP3 = Jackpot, P6 = Pick 6, PA = Place Accumulator.
POOL_LEG_COUNTS: Dict[str, int] = {"BI": 6, "JP": 4, "P6": 6, "PA": 7}
POOL_LABELS: Dict[str, str] = {
    "BI": "BIPOT",
    "JP": "JACKPOT",
    "P6": "PICK 6",
    "PA": "PLACE ACCUMULATOR",
}


def resolve_pool_legs(pool_code: str) -> Tuple[str, int]:
    """Resolve an extracted pool code (e.g. 'JP1', 'BI2', 'P6', 'PA') to
    (display_label, leg_count). Unknown codes default to a 4-leg Jackpot."""
    code = (pool_code or "").upper()
    prefix = next((p for p in POOL_LEG_COUNTS if code.startswith(p)), None)
    return POOL_LABELS.get(prefix, "JACKPOT"), POOL_LEG_COUNTS.get(prefix, 4)


def convention_pool_starts(total_races: int) -> Dict[str, int]:
    """TAB-standard pool start races per card size — FALLBACK ONLY.

    PDF leg_info and the TAB tipping sheet always win when present; this
    table is used only when neither exists. Single source of truth shared
    by strike_tips exotic analysis and build_exotics_blueprint (Sep-2026:
    two disagreeing tables carded Bipot R2-7 on an 8-race Greyville card
    that TAB runs as R1-6).
    """
    if total_races >= 10:
        return {"BI1": 2, "PA": 3, "P6": 4, "JP1": 4, "JP2": 7}
    if total_races == 9:
        # TAB standard (Fairview/Durbanville 9-race cards): BI R2-7,
        # PA R3-9, P6 R4-9, JP R5-8 + R6-9.
        return {"BI1": 2, "PA": 3, "P6": 4, "JP1": 5, "JP2": 6}
    if total_races == 8:
        return {"BI1": 1, "PA": 2, "P6": 3, "JP1": 4, "JP2": 5}
    if total_races >= 6:
        return {"BI1": 1, "P6": 1, "JP1": 3}
    return {"JP1": 1}


def build_exotics_blueprint(races: List[Dict]) -> Tuple[Dict, Dict]:
    total_races = len(races)
    race_map = {r["number"]: r for r in races}

    pool_starts = {}
    for race in races:
        for p in race["pools"]:
            key = p
            if p == "BIPOT":
                key = "BI1"
            if p == "JACKPOT":
                key = "JP1"
            if key not in pool_starts:
                pool_starts[key] = race["number"]

    for _code, _start in convention_pool_starts(total_races).items():
        if _code not in pool_starts:
            pool_starts[_code] = _start

    if "JP3" not in pool_starts and total_races >= 12:
        pool_starts["JP3"] = 9

    if "BI2" not in pool_starts and total_races >= 12:
        pool_starts["BI2"] = 7

    blueprints = {}

    def get_selections_for_legs(start_race: int, num_legs: int) -> List[Dict]:
        legs = []
        for leg_idx in range(num_legs):
            target_race_num = start_race + leg_idx
            race = race_map.get(target_race_num)
            if race and race["runners"]:
                sorted_runners = sorted(race["runners"], key=lambda r: r.get("prob", 0.0), reverse=True)
                banker = sorted_runners[0]
                savers = sorted_runners[1:3]
                legs.append({
                    "race": target_race_num,
                    "banker": banker,
                    "savers": savers,
                })
        return legs

    pool_configs = [
        ("Jackpot 1", "JP1", 4),
        ("Jackpot 2", "JP2", 4),
        ("Jackpot 3", "JP3", 4),
        ("Bipot 1", "BI1", 6),
        ("Bipot 2", "BI2", 6),
        ("Place Accumulator", "PA", 7),
        ("Pick 6", "P6", 6),
    ]

    for pool_name, key, num_legs in pool_configs:
        if key in pool_starts:
            legs = get_selections_for_legs(pool_starts[key], num_legs)
            if legs:
                blueprints[pool_name] = legs

    return blueprints, pool_starts


# ── Textbook doctrine (exotics-construction.md, Oct-2026) ────────────────
# TAB leg_info stays the data source of truth; these rules SHAPE the ticket.

def leg_uncertainty(runners: List[Dict]) -> float:
    """Murky-leg score: tight top-3 probs + big field = chaos.

    0.0 = standout banker territory; higher = wider coverage deserved.
    Pure function over probabilities — no I/O, fully testable.
    """
    if not runners:
        return 0.0
    probs = sorted((float(r.get("prob") or 0.0) for r in runners), reverse=True)
    top = probs[0] if probs else 0.0
    third = probs[2] if len(probs) > 2 else 0.0
    gap = max(0.0, top - third)
    # Tight top-3 (gap < 0.10) scores high; big fields add chaos weight.
    tightness = max(0.0, 1.0 - gap / 0.10)
    field = min(1.0, len(probs) / 16.0)
    return round(0.7 * tightness + 0.3 * field, 3)


def widen_murkiest_legs(
    legs: List[Dict],
    race_map: Dict[int, Dict],
    budget: int = 1,
) -> List[Dict]:
    """Add one extra saver (4th horse) to the `budget` murkiest legs.

    Textbook prime directive: a ticket dies in its thinnest leg relative to
    chaos, so spare coverage goes there — never spread evenly. Mutates copies,
    never the input legs.
    """
    if budget <= 0 or not legs:
        return legs
    scored = []
    for leg in legs:
        race = race_map.get(leg["race"], {})
        runners = race.get("runners", [])
        covered = {leg["banker"].get("name")} | {s.get("name") for s in leg.get("savers", [])}
        scored.append((leg_uncertainty(runners), leg, runners, covered))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = [dict(leg, savers=list(leg.get("savers", []))) for leg in legs]
    by_race = {leg["race"]: leg for leg in out}
    spent = 0
    for _, leg, runners, covered in scored:
        if spent >= budget:
            break
        ordered = sorted(runners, key=lambda r: float(r.get("prob") or 0.0), reverse=True)
        extra = next((r for r in ordered if r.get("name") not in covered), None)
        if extra is None:
            continue
        target = by_race[leg["race"]]
        target["savers"].append(extra)
        target["widened"] = True
        spent += 1
    return out


def apply_flagged_horses(
    legs: List[Dict],
    flagged: Dict[int, List[str]],
) -> List[Dict]:
    """Flagged horses auto-qualify (Friday-night doctrine): any runner the
    analysis flagged in a ticket leg MUST appear on the ticket — displacing
    the weakest saver if needed. Names matched case-insensitively."""
    if not flagged:
        return legs
    out = [dict(leg, savers=list(leg.get("savers", []))) for leg in legs]
    for leg in out:
        wants = flagged.get(leg["race"], [])
        if not wants:
            continue
        covered = {leg["banker"].get("name", "").lower()} | {
            s.get("name", "").lower() for s in leg["savers"]
        }
        for name in wants:
            if name.lower() in covered:
                continue
            if leg["savers"]:
                leg["savers"][-1] = {"name": name, "flagged": True}
            else:
                leg["savers"].append({"name": name, "flagged": True})
            covered.add(name.lower())
        leg["flagged_applied"] = True
    return out


# Single-race pool suitability gate (picked races only — exotics-pools.md).
# Quartet wants chaos (12+), Trifecta a readable mid-field (8+) with a
# confident winner, Exacta a duel. Returns pool -> construction hint.
def race_suitability(race: Dict) -> Dict[str, str]:
    runners = race.get("runners", [])
    n = len(runners)
    if n < 2:
        return {}
    probs = sorted((float(r.get("prob") or 0.0) for r in runners), reverse=True)
    top = probs[0] if probs else 0.0
    out: Dict[str, str] = {}
    if n >= 4:
        out["Exacta"] = "box" if n <= 8 and top < 0.45 else "single-or-box"
    if n >= 8:
        out["Trifecta"] = "multi-banker-1st" if top >= 0.35 else "box"
    if n >= 12:
        out["Quartet"] = "box-or-float"
    return out
