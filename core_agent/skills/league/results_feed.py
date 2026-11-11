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
import logging
import os
import re
import time
from datetime import date as _date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from .regions import region_of
from .settlement import _read_jsonl, _track_key

logger = logging.getLogger("league-results-feed")

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

    Every record is ``{date, course, race_number, off_time, runners: [...]}``
    where each runner is ``{number, name, position, odds_decimal}``. Races
    whose result table cannot be read are skipped, never approximated.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    races: List[Dict[str, Any]] = []
    off_times = _off_times_from_html(soup)

    for section in soup.find_all(id=re.compile(r"^race-\d+$")):
        race_number = section.get("id", "").split("-", 1)[1]
        table = None
        for cand in section.find_all("table"):
            headers = [th.get_text(" ", strip=True).lower() for th in cand.find_all("th")]
            if "finish" in headers and "horse" in headers and "odds" in headers:
                table = cand
                break
        if table is None:
            # A refunded / abandoned race publishes no result table at all.
            # Without this branch the race vanished from the card entirely and
            # every pick on it stayed pending forever (Nov-2026 Turffontein
            # R9/R10, abandoned for heavy rain). Record the void explicitly so
            # settlement can refund the pick instead of waiting for a winner
            # that will never exist.
            text = section.get_text(" ", strip=True).lower()
            reason = None
            if "race refunded" in text or re.search(r"\brefund", text):
                reason = "refunded"
            elif "abandoned" in text:
                reason = "abandoned"
            elif "void" in text:
                reason = "void"
            if reason:
                races.append({
                    "date": date,
                    "course": course,
                    "race_number": str(race_number),
                    "runners": [],
                    "void": True,
                    "void_reason": reason,
                    "source": "raceform",
                })
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
                # The raw finish cell is kept so a consumer can tell a
                # SCRATCHED horse (no finish, never ran) from a FALLER ("F",
                # ran and did not finish) — both have no finishing position.
                "finish_raw": cells[col["finish"]].get_text(" ", strip=True),
                "odds_decimal": parse_odds(cells[col["odds"]].get_text(" ", strip=True)),
            })

        if any(r["position"] == 1 for r in runners):
            races.append({
                "date": date,
                "course": course,
                "race_number": str(race_number),
                "off_time": off_times.get(str(race_number), ""),
                "runners": runners,
                "source": "raceform",
            })

    return races


def _off_times_from_html(soup) -> Dict[str, str]:
    """{race_number: "HH:MM"} from the meeting's winners-glance rows.

    Raceform's card header lists every race with its off time ("R1 12:37").
    The results tables themselves do not carry it, and the ATR-shaped title
    ("N HH:MM ...") is how the settlement code keys a race number.
    """
    out: Dict[str, str] = {}
    try:
        for row in soup.select("a.winners-glance-row"):
            href = row.get("href") or ""
            m = re.search(r"#race-(\d+)", str(href))
            if not m:
                continue
            small = row.select_one(".wg-race small")
            clock = small.get_text(" ", strip=True) if small else ""
            if clock and re.match(r"^\d{1,2}:\d{2}$", clock):
                out[m.group(1)] = clock
    except Exception as e:
        logger.debug("off times not read: %s", e)
    return out


_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(pos: Any) -> str:
    """1 -> "1st", 4 -> "4th" (the shape ATR results use)."""
    try:
        n = int(pos)
    except (TypeError, ValueError):
        return str(pos or "")
    if n <= 0:
        return ""
    if n in _ORDINALS:
        return _ORDINALS[n]
    return f"{n}th"


def confirmed_results_as_races(data_dir: str) -> List[Dict[str, Any]]:
    """The confirmed SA cards as ATR-shaped race records.

    The HUD's results tab renders ATR records, and ATR covers SA only while
    its browser tier is allowed through (it is blocked for long stretches).
    Raceform's cards are server-rendered HTML and always work, so the SA
    meeting is served from here: full finishing order plus SP for every race
    of the day, even while ATR is challenged.
    """
    out: List[Dict[str, Any]] = []
    for row in load_confirmed_results(data_dir):
        race_no = str(row.get("race_number") or "").strip()
        if not race_no:
            continue
        off = str(row.get("off_time") or "").strip()
        runners = []
        for r in row.get("runners") or []:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name") or "").strip()
            if not name:
                continue
            runners.append({
                "name": name,
                "position": _ordinal(r.get("position")),
                "odds_decimal": r.get("odds_decimal"),
                "form": "",
            })
        if not runners:
            continue
        out.append({
            "course": str(row.get("course") or ""),
            "date": str(row.get("date") or "")[:10],
            "time": off,
            "title": f"{race_no} {off}".strip(),
            "runners": runners,
            "source": "raceform",
        })
    return out


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def meeting_date_from_html(html: str) -> Optional[str]:
    """The meeting date Raceform actually displays (ISO), or None.

    Raceform's results page heads the card with the meeting it is showing:
    "Tuesday 10 November 2026" and the race count.
    """
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(html, "html.parser")
        head = soup.find(class_="winners-glance-head")
        h2 = head.find("h2") if head else None
        text = h2.get_text(" ", strip=True) if h2 else ""
    except Exception:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if not m:
        return None
    day, month, year = m.groups()
    mi = _MONTHS.get(month.strip().lower())
    if not mi:
        return None
    try:
        return f"{int(year):04d}-{mi:02d}-{int(day):02d}"
    except (TypeError, ValueError):
        return None


def fetch_meeting(course: str, date: str, timeout: float = 25.0) -> List[Dict[str, Any]]:
    """Download and parse one meeting. Raises on network failure.

    Raceform IGNORES the date in the URL and serves the LATEST meeting for
    that course — asking for "kenilworth/2026-11-04" returns today's card
    (Nov-2026). Stamping that card with the requested date would settle a
    past pick against another day's runners, so the displayed meeting date
    is checked first and a mismatch yields NO results at all.
    """
    import httpx

    slug = _track_key(course).replace(" ", "-")
    url = f"{BASE_URL}/{slug}/{date}"
    resp = httpx.get(
        url, headers={"User-Agent": _UA}, timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    shown = meeting_date_from_html(resp.text)
    if shown and shown != str(date)[:10]:
        logger.warning(
            "Raceform served %s %s for the %s request — refusing the card",
            course, shown, date,
        )
        return []
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
        # A void race carries no winner by definition; the position check below
        # would silently drop it and leave its picks pending forever.
        if not race.get("void") and not any(
            r.get("position") == 1 for r in race.get("runners") or []
        ):
            continue
        # Keep the RICHER card for a race. A fetch taken while the race was
        # still running can parse a single row (the winner), and letting that
        # partial card replace a full one made the league read "not on the
        # card" as "outside the top 4" (Nov-2026: Skip The Line, 2nd in
        # Fairview R1, settled a loss from a one-runner card).
        prev = by_key.get(key)
        if (
            prev is None
            or race.get("void")
            or len(race.get("runners") or []) >= len(prev.get("runners") or [])
        ):
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

# How long a meeting is left alone after it was fetched. A card fills in
# race by race as the meeting runs, so the meeting has to be re-fetched —
# but an abandoned race never gets a result, and re-fetching it every cycle
# would hammer Raceform forever.
FETCH_COOLDOWN_SECS = 20 * 60
_FETCH_MARKERS = "results_fetch_markers.json"


def _fetch_markers(data_dir: str) -> Dict[str, float]:
    path = os.path.join(data_dir, _FETCH_MARKERS)
    try:
        with open(path) as f:
            data = json.load(f)
        return {str(k): float(v) for k, v in (data or {}).items()}
    except Exception:
        return {}


def _mark_fetched(data_dir: str, day: str, course: str) -> None:
    path = os.path.join(data_dir, _FETCH_MARKERS)
    markers = _fetch_markers(data_dir)
    markers[f"{day}|{_track_key(course)}"] = time.time()
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(markers, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception as e:
        logger.debug("fetch marker not written: %s", e)


def pending_meetings(
    data_dir: str, days: int = 3, today: Optional[_date] = None,
    cooldown_secs: int = FETCH_COOLDOWN_SECS,
) -> List[tuple]:
    """(date, course) pairs with picks still pending and a Raceform page.

    Granularity is PER RACE, not per meeting: a meeting's card fills in
    race by race while the day runs, so a meeting that already has R1-R4
    confirmed still needs a fetch for R5-R9 (Nov-2026: Kenilworth was
    fetched once at 13:07 and the rest of the card never arrived — the
    meeting was considered "already have" and every later race stayed
    pending forever).

    Re-fetches are rate-limited per meeting, so a race that will never have
    a result (abandoned) cannot turn into a Raceform request every cycle.
    """
    today = today or datetime.now().date()
    floor = today - timedelta(days=days)
    have = {_result_key(r) for r in load_confirmed_results(data_dir)}
    markers = _fetch_markers(data_dir)
    now = time.time()
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
        race = str(row.get("race_number") or "").strip()
        if (day, _track_key(course), race) in have:
            continue  # this race already has a confirmed card
        last = markers.get(f"{day}|{_track_key(course)}")
        if last and (now - last) < cooldown_secs:
            continue  # fetched recently; wait before asking again
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
            _mark_fetched(data_dir, day, course)
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
