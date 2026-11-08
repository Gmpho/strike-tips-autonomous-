"""Manual / operator ingestion CLI for race results into confirmed_results.jsonl.

Enables instant confirmation of race finishes (with SP and 1st-4th placing)
and immediate settlement of open league picks, bypassing scraper blocks.

Usage:
------
# Ingest single race finish:
python -m core_agent.skills.league.ingest_card \
    --course doncaster --date 2026-11-06 --race 1 \
    --winner "Horse Name" --sp 3.5 \
    --place2 "Second Horse" --place3 "Third Horse" --place4 "Fourth Horse"

# Ingest multiple races from a JSON file:
python -m core_agent.skills.league.ingest_card --file results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from core_agent.skills.league.results_feed import append_confirmed_results
from core_agent.skills.league.settlement import settle_open_picks

DATA_DIR = os.environ.get("DATA_DIR", "data")


def ingest_single_race(
    data_dir: str,
    course: str,
    date: str,
    race_number: str | int,
    winner: str,
    sp: Optional[float] = None,
    place2: Optional[str] = None,
    place3: Optional[str] = None,
    place4: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingest a single race card with top finishers and trigger settlement."""
    runners: List[Dict[str, Any]] = [
        {"number": 1, "name": winner.strip(), "position": 1, "odds_decimal": sp}
    ]
    if place2:
        runners.append({"number": 2, "name": place2.strip(), "position": 2, "odds_decimal": None})
    if place3:
        runners.append({"number": 3, "name": place3.strip(), "position": 3, "odds_decimal": None})
    if place4:
        runners.append({"number": 4, "name": place4.strip(), "position": 4, "odds_decimal": None})

    card = {
        "date": str(date)[:10],
        "course": course.strip(),
        "race_number": str(race_number).strip(),
        "runners": runners,
        "source": "cli_operator",
    }
    written = append_confirmed_results(data_dir, [card])
    settle_stats = settle_open_picks(data_dir)
    return {
        "ok": True,
        "races_ingested": written,
        "settlement": settle_stats,
    }


def ingest_from_file(data_dir: str, file_path: str) -> Dict[str, Any]:
    """Ingest race cards from a JSON file and trigger settlement."""
    with open(file_path, "r") as f:
        data = json.load(f)
    races = data if isinstance(data, list) else data.get("races", [])
    if not races:
        return {"ok": False, "error": "No races found in file"}
    written = append_confirmed_results(data_dir, races)
    settle_stats = settle_open_picks(data_dir)
    return {
        "ok": True,
        "races_ingested": written,
        "settlement": settle_stats,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest confirmed race results for settlement.")
    parser.add_argument("--course", help="Track name (e.g. doncaster, aintree, greyville)")
    parser.add_argument("--date", help="Meeting date (YYYY-MM-DD)")
    parser.add_argument("--race", help="Race number (e.g. 1)")
    parser.add_argument("--winner", help="Winner horse name")
    parser.add_argument("--sp", type=float, help="Starting price decimal (e.g. 3.5)")
    parser.add_argument("--place2", help="2nd place horse name")
    parser.add_argument("--place3", help="3rd place horse name")
    parser.add_argument("--place4", help="4th place horse name")
    parser.add_argument("--file", help="Path to JSON file with array of race cards")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="Data directory path")

    args = parser.parse_args(argv)

    if args.file:
        res = ingest_from_file(args.data_dir, args.file)
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if not (args.course and args.date and args.race and args.winner):
        parser.error("Either --file OR (--course, --date, --race, and --winner) are required.")

    res = ingest_single_race(
        data_dir=args.data_dir,
        course=args.course,
        date=args.date,
        race_number=args.race,
        winner=args.winner,
        sp=args.sp,
        place2=args.place2,
        place3=args.place3,
        place4=args.place4,
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
