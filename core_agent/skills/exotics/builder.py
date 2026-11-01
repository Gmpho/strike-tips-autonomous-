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

    if "BI1" not in pool_starts:
        pool_starts["BI1"] = 2 if total_races >= 10 else 1

    if "PA" not in pool_starts:
        pool_starts["PA"] = 3 if total_races >= 12 else 2

    if "P6" not in pool_starts:
        if total_races >= 12:
            pool_starts["P6"] = 4
        elif total_races in (9, 10):
            pool_starts["P6"] = 3
        else:
            pool_starts["P6"] = 3

    if "JP1" not in pool_starts:
        if total_races >= 12:
            pool_starts["JP1"] = 1
        elif total_races in (9, 10):
            pool_starts["JP1"] = 4
        else:
            pool_starts["JP1"] = 5

    if "JP2" not in pool_starts and total_races >= 9:
        pool_starts["JP2"] = 5 if total_races >= 12 else 6

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
