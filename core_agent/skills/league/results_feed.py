"""Official race-result feed for the predictor league.

Settlement may only use **confirmed** results. Two sources already exist —
`settled_winners.jsonl` (winner name only, written by `result_tracker`) and
`atr_results_snapshot.json` (a rolling card of one day's meetings) — but both
regularly miss South African meetings. When they do, every pick at that
meeting stays pending forever (Nov-2026: 30 picks stuck).

Raceform publishes the full official card for every SA meeting — finishing
position, saddle number and starting price for every runner. Ingesting that
into `confirmed_results.jsonl` gives settlement a dated, permanent source that
can also score 2nd and 3rd, which a winner-only archive cannot.

Read-only against the web, append-only against the volume: nothing here
touches the bankroll governor, `result_tracker` or the bets ledger.

CLI
---
    python -m core_agent.skills.league.results_feed \
        --course greyville --date 2026-11-06
    python -m core_agent.skills.league.results_feed --backfill --data-dir data
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date as _date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from .regions import region_of
from .settlement import _read_jsonl, _track_key

RESULTS_FILENAME = "confirmed_results.jsonl"
BASE_URL = "https://raceform.co.za/horse-racing-results"
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Raceform covers the SA tracks the league actually picks from. "clairwood"
# is a historic track with no current meetings, so it is not listed.
RACEFORM_COURSES = {
    "turffontein", "vaal", "fairview", "scottsville", "kenilworth",
    "greyville", "durbanville",
}


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_odds(raw: Any) -> Optional[float]:
    """'33/1' -> 34.0, '9/20' -> 1.45, 'EVS' -> 2.0, '1.50' -> 1.5.

    Returns None for anything unparseable so the caller can decide — a missing
    price must never be guessed into a points bonus.
    """
    s = str(raw or "").strip().lower().replace("r", "").replace(",", "")
    if not s or s in ("-", "sp", "n/a"):
        return None
    if s in ("evs", "evens", "even"):
        return 2.0
    if "/" in s:
        a, _, b = s.partition("/")
        try:
            num, den = float(a), float(b)
        except ValueError:
            return None
        if num <= 0 or den <= 0:
            return None
        return round(num / den + 1.0, 3)
    try:
        val = float(s)
    except ValueError:
        return None
    return val if val > 1 else None


def parse_finish(raw: Any) -> Optional[int]:
    """'1'/'1st' -> 1; a non-finish code ('PU', 'UR', 'F', '0') -> None."""
    s = str(raw or "").strip().lower()
    m = re.match(r"^(\d+)", s)
    if not m:
        return None
    n = int(m.group(1))
    return n if n > 0 else None


def _horse_name(cell: Any) -> str:
    """Prefer the horse link text; fall back to stripping 'age colour sex'."""
    link = cell.find("a", href=re.compile(r"^/horses/"))
    if link:
        return link.get_text(" ", strip=True)
    text = cell.get_text(" ", strip=True)
    return re.sub(r"\s+\d{1,2}\s+[a-z]{1,3}\s+[a-z]{1,3}$", "", text).strip()


def parse_meeting_html(
    html: str, course: str, date: str
) -> List[Dict[str, Any]]:
    """Parse one Raceform results page into confirmed race records.

    Every record is ``{date, course, race_number, runners: [...]}`` where each
    runner is ``{number, name, position, odds_decimal}``. Races whose result
    table cannot be read are skipped, never approximated.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    races: List[Dict[str, Any]] = []

    for section in soup.find_all(id=re.compile(r"^race-\d+$")):
        race_number = section.get("id", "").split("-", 1)[1]
        table = None
        for cand in section.find_all("table"):
            headers = [th.get_text(" ", strip=True).lower() for th in cand.find_all("th")]
            if "finish" in headers and "horse" in headers and "odds" in headers:
                table = cand
                break
        if table is None:
            continue

        header_cells = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        try:
            col = {name: header_cells.index(name) for name in
                   ("finish", "no", "horse", "odds")}
        except ValueError:
            continue

        runners: List[Dict[str, Any]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) <= max(col.values()):
                continue
            name = _horse_name(cells[col["horse"]])
            if not name:
                continue
            try:
                number = int(re.sub(r"\D", "", cells[col["no"]].get_text(" ", strip=True)) or 0)
            except ValueError:
                number = 0
            runners.append({
                "number": number,
                "name": name,
                "position": parse_finish(cells[col["finish"]].get_text(" ", strip=True)),
                "odds_decimal": parse_odds(cells[col["odds"]].get_text(" ", strip=True)),
            })

        if any(r["position"] == 1 for r in runners):
            races.append({
                "date": date,
                "course": course,
                "race_number": str(race_number),
                "runners": runners,
                "source": "raceform",
            })

    return races


def fetch_meeting(course: str, date: str, timeout: float = 25.0) -> List[Dict[str, Any]]:
    """Download and parse one meeting. Raises on network failure."""
    import httpx

    slug = _track_key(course).replace(" ", "-")
    url = f"{BASE_URL}/{slug}/{date}"
    resp = httpx.get(
        url, headers={"User-Agent": _UA}, timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    return parse_meeting_html(resp.text, course, date)


# ── storage ──────────────────────────────────────────────────────────────────

def _result_key(row: Dict[str, Any]) -> tuple:
    return (
        str(row.get("date") or "")[:10],
        _track_key(row.get("course") or row.get("track")),
        str(row.get("race_number") or row.get("race") or "").strip(),
    )


def load_confirmed_results(data_dir: str) -> List[Dict[str, Any]]:
    """Every confirmed card on the volume, latest write wins per race."""
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for row in _read_jsonl(os.path.join(data_dir, RESULTS_FILENAME)):
        key = _result_key(row)
        if all(key):
            by_key[key] = row
    return list(by_key.values())


def append_confirmed_results(data_dir: str, races: Iterable[Dict[str, Any]]) -> int:
    """Merge race cards into `confirmed_results.jsonl` atomically.

    Re-ingesting the same meeting replaces its rows instead of duplicating
    them, so the feed can be re-run safely (a corrected card always wins).
    """
    path = os.path.join(data_dir, RESULTS_FILENAME)
    by_key: Dict[tuple, Dict[str, Any]] = {
        _result_key(r): r for r in load_confirmed_results(data_dir)
    }
    added = 0
    for race in races:
        key = _result_key(race)
        if not all(key):
            continue
        if not any(r.get("position") == 1 for r in race.get("runners") or []):
            continue
        by_key[key] = race
        added += 1
    if not added:
        return 0

    os.makedirs(data_dir, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for key in sorted(by_key):
            f.write(json.dumps(by_key[key]) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return added


# ── backfill ─────────────────────────────────────────────────────────────────

def pending_meetings(
    data_dir: str, days: int = 3, today: Optional[_date] = None
) -> List[tuple]:
    """(date, course) pairs with picks still pending and a Raceform page."""
    today = today or datetime.now().date()
    floor = today - timedelta(days=days)
    have = {(_result_key(r)[0], _result_key(r)[1]) for r in load_confirmed_results(data_dir)}
    out = set()
    for row in _read_jsonl(os.path.join(data_dir, "league_picks.jsonl")):
        if row.get("settled"):
            continue
        course = str(row.get("course") or "")
        day = str(row.get("date") or "")[:10]
        if not course or not day:
            continue
        if _track_key(course) not in RACEFORM_COURSES or region_of(course) != "SA":
            continue
        try:
            if datetime.fromisoformat(day).date() < floor:
                continue
        except ValueError:
            continue
        if (day, _track_key(course)) in have:
            continue
        out.add((day, course))
    return sorted(out)


def backfill_missing_results(
    data_dir: str, days: int = 3, limit: int = 6,
    today: Optional[_date] = None,
) -> Dict[str, Any]:
    """Fetch official cards for SA meetings that still have pending picks.

    Fully guarded: a network or markup failure leaves picks pending (they are
    never settled from a guess) and is reported in ``errors``.
    """
    stats: Dict[str, Any] = {"meetings": 0, "races": 0, "errors": []}
    for day, course in pending_meetings(data_dir, days=days, today=today)[:limit]:
        try:
            races = fetch_meeting(course, day)
            stats["meetings"] += 1
            stats["races"] += append_confirmed_results(data_dir, races)
        except Exception as exc:  # network, markup drift, rate limit
            stats["errors"].append(f"{day} {course}: {str(exc)[:120]}")
    return stats


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest confirmed race results")
    ap.add_argument("--course", help="track name, e.g. greyville")
    ap.add_argument("--date", help="meeting date, YYYY-MM-DD")
    ap.add_argument("--backfill", action="store_true",
                    help="fetch SA meetings that still have pending picks")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    args = ap.parse_args(argv)

    if args.backfill:
        print(json.dumps(backfill_missing_results(args.data_dir, days=args.days), indent=2))
        return 0

    if not (args.course and args.date):
        ap.error("--course and --date are required unless --backfill is used")

    races = fetch_meeting(args.course, args.date)
    if not races:
        print(f"no parsable results for {args.course} {args.date}")
        return 1
    written = append_confirmed_results(args.data_dir, races)
    winners = {
        r["race_number"]: next(
            (x["name"] for x in r["runners"] if x["position"] == 1), "?"
        )
        for r in races
    }
    print(json.dumps({"written": written, "winners": winners}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
