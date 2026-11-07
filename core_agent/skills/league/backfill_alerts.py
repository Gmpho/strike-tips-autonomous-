"""Backfill league picks from the alert_history archive.

Each odds-drop alert we sent (course, horse, odds, race, off) becomes a
candidate pick. We join against settled_winners.jsonl to determine win/loss.
Unresolvable rows are excluded — never fabricated.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Set

from .regions import region_of


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def load_alerts(data_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    # current + archived
    for name in os.listdir(data_dir):
        if not name.startswith("alert_history"):
            continue
        if not (name.endswith(".json") or name.endswith(".jsonl")):
            continue
        p = os.path.join(data_dir, name)
        # try JSON array first
        try:
            d = json.load(open(p))
            if isinstance(d, list):
                rows += d
                continue
        except Exception:
            pass
        # fall back to JSONL
        rows += _read_jsonl(p)
    return rows


def load_winners(data_dir: str) -> Dict[str, str]:
    """Map (track_lower, race) -> winner name."""
    m: Dict[str, str] = {}
    for row in _read_jsonl(os.path.join(data_dir, "settled_winners.jsonl")):
        key = (str(row.get("track", "")).strip().lower(), str(row.get("race", "")).strip())
        m[key] = str(row.get("winner", "")).strip()
    return m


def build_picks(data_dir: str) -> List[Dict[str, Any]]:
    alerts = load_alerts(data_dir)
    winners = load_winners(data_dir)
    seen: Set[tuple] = set()
    out: List[Dict[str, Any]] = []
    for a in alerts:
        course = str(a.get("course", "")).strip()
        horse = str(a.get("horse", "")).strip()
        race = str(a.get("race", "")).strip()
        odds = a.get("odds")
        if not course or not horse or not race or not odds:
            continue
        try:
            odds = float(odds)
        except Exception:
            continue
        if odds <= 1:
            continue
        key = (course.lower(), race, horse.lower())
        if key in seen:
            continue
        seen.add(key)
        winner = winners.get((course.lower(), race))
        if winner is None:
            continue  # unresolvable -> exclude
        won = winner.lower() == horse.lower()
        out.append({
            "entity_type": "cohort",
            "entity_id": f"alert:{course.lower()}",
            "entity_name": f"{course.title()} alerts",
            "region": region_of(course),
            "date": str(a.get("timestamp", ""))[:10],
            "settled": True,
            "won": won,
            "points": int(round(odds)) if won else 0,
            "winner_sp": odds if won else 0.0,
            "pick_odds": odds,
            "dedup_key": f"{course.lower()}|{race}|{horse.lower()}",
        })
    return out


def _load_existing_keys(path: str) -> set:
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if row.get("dedup_key"):
                    keys.add(row["dedup_key"])
            except Exception:
                continue
    return keys


def apply_picks(data_dir: str) -> dict:
    """Idempotently append backfilled picks to league_picks.jsonl."""
    picks = build_picks(data_dir)
    log_path = os.path.join(data_dir, "league_picks.jsonl")
    existing = _load_existing_keys(log_path)
    new_rows = [p for p in picks if p.get("dedup_key") not in existing]
    os.makedirs(data_dir, exist_ok=True)
    with open(log_path, "a") as f:
        for p in new_rows:
            f.write(json.dumps(p) + "\n")
    return {"built": len(picks), "new": len(new_rows), "skipped": len(picks) - len(new_rows)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", nargs="?", default="/app/data")
    ap.add_argument("--apply", action="store_true", help="write to league_picks.jsonl")
    args = ap.parse_args()
    if args.apply:
        print(json.dumps(apply_picks(args.data_dir), indent=2))
    else:
        picks = build_picks(args.data_dir)
        print(json.dumps({"count": len(picks), "wins": sum(1 for p in picks if p["won"])}, indent=2))
