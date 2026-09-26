"""
Result Tracker - Auto-settle open bets using search service (DDGS + direct SA scraper).
Uses fuzzy matching on horse names with date fallback (today → yesterday → no date).
"""

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from html import unescape as _html_unescape
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("result-tracker")

# South Africa has no daylight saving — fixed UTC+2, safe without tzdata.
_SAST = timezone(timedelta(hours=2))

# Words that generic snippets use around results ("1st choice", "the
# favourite won") but which are never actual horse names on their own.
# _extract_race_winner must reject single-word captures from this set —
# otherwise any snippet settles the bet LOST against a phantom winner.
_NON_NAME_WORDS = frozenset({
    "choice", "choices", "favourite", "favourites", "favorite", "favorites",
    "pick", "picks", "tip", "tips", "selection", "selections", "nap", "nb",
    "each", "way", "double", "treble", "yankee", "lucky", "patent", "trixie",
    "outsider", "longshot", "banker", "saver", "field", "rest", "others",
    "rival", "rivals", "danger", "dangers", "threat", "contender", "winner",
    "winners", "winning", "won", "first", "second", "third", "placed",
    "horse", "horses", "runner", "runners", "race", "races", "track",
    "south", "africa", "result", "results",
})

# Grace period after scheduled off-time before a race counts as runnable for
# settlement (results need time to publish).
OFF_TIME_GRACE_MINUTES = 15


# Max age for AUTO-settlement. Older PENDING bets are left alone for manual
# review: settling a week-old bet against yesterday's results for the same
# track+race number would usually settle the WRONG race (usually as LOST).
MAX_SETTLE_AGE_DAYS = 3

# Exotics get a wider window than singles: the Raceform archive
# (/horse-racing-results/{track}/{date}, plain HTTP, no CF challenge) serves
# SA meetings by exact date ~2 weeks back, so a historical ticket is only
# ever scored against ITS OWN race day. Beyond this bound no source can prove
# that day anymore — the ticket is expired/deferred for manual review, never
# guessed.
EXOTIC_MAX_AGE_DAYS = 14


def _healing_event(
    action: str, details: str, agent: str = "ResultTracker", status: str = "SUCCESS"
) -> None:
    """Append a healing event so blockers show up in Live Ops instead of
    living only in container logs (e.g. a won exotic awaiting its dividend).
    Mirrors the monitor's event shape; never raises."""
    try:
        from core_agent.config.paths import DATA_DIR

        path = DATA_DIR / "healing_events.json"
        events = []
        if os.path.exists(path):
            try:
                with open(path) as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    events = loaded
            except Exception:
                events = []
        events.append({
            "id": f"{action.lower()}-{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "agent": agent,
            "status": status,
        })
        tmp = str(path) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(events[-50:], f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except Exception:
        pass


def _finish_ordinal(n) -> Optional[str]:
    """\"1st\"/\"2nd\"/\"3rd\"/... for a finishing position, None for non-finishers.

    Raceform stamps runners that did not complete with ``finish: 0`` — they
    can satisfy no pool requirement, so they get no ordinal (ATR-shaped
    runners carry \"\" for unknown/unplaced positions too).
    """
    try:
        n = int(n)
    except (ValueError, TypeError):
        return None
    if n <= 0:
        return None
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _norm_name(value: str) -> str:
    """Punctuation-insensitive name tokens.

    Books disagree on punctuation ("Captain's Elect" vs "Captains
    Elect"); overlap scoring must never hinge on an apostrophe —
    2026-09-23 Durbanville BIPOT was falsely LOST on exactly that.
    """
    return re.sub(r"[^a-z0-9\s]", "", str(value or "").lower())


def _log_settled_winner(bet, winner: str) -> None:
    """Append a confirmed winner for dream calibration.

    Best-effort JSONL ({date, track, race, winner}) on the first writable
    data dir found. Never raises.
    """
    try:
        data_dir = ""
        for cand in (os.environ.get("DATA_DIR", ""), "./data", "data",
                     "/app/data"):
            if cand and os.path.isdir(cand):
                data_dir = cand
                break
        if not data_dir:
            return
        with open(os.path.join(data_dir, "settled_winners.jsonl"), "a") as f:
            f.write(json.dumps({
                "date": str(getattr(bet, "date", "") or "")[:10],
                "track": str(getattr(bet, "track", "") or ""),
                "race": str(getattr(bet, "race_number", "") or ""),
                "winner": str(winner or ""),
            }) + "\n")
    except Exception as e:
        logger.debug(f"settled-winner log skipped: {e}")


def _bet_age_days(bet_date: Optional[str]) -> Optional[int]:
    """Age of a bet in days from its ISO date, or None if unparseable."""
    if not bet_date:
        return None
    try:
        return (date.today() - date.fromisoformat(str(bet_date)[:10])).days
    except (ValueError, TypeError):
        return None


def _is_exotic_bet(bet) -> bool:
    """Exotic pool tickets (PICK6:1-2-3..., confidence EXOTIC) can't be settled
    from single-winner results — they need pool dividends. Skip them here."""
    try:
        if str(getattr(bet, "confidence", "") or "").upper() == "EXOTIC":
            return True
        return ":" in str(getattr(bet, "horse", "") or "")
    except Exception:
        return False


def _rf_text(page: str) -> str:
    """Normalise a Raceform page for regex parsing.

    The same data appears twice: HTML-entity encoded inside Livewire
    ``wire:snapshot`` attributes (&quot;) and JSON-escaped in embedded JS
    (\\", \\/). Unescape both so one regex set matches either copy.
    """
    return _html_unescape(str(page or "")).replace("\\/", "/").replace('\\"', '"')


def _raceform_url(track: Optional[str], iso_date: Optional[str]) -> Optional[str]:
    """Raceform archive URL for one track+date, None when inputs are invalid.

    Path shape verified live (Sep-2026): /horse-racing-results/{track}/{date}
    returns the full meeting page as plain HTML — unlike ATR, which serves
    only today/yesterday labels and 404s on ISO dates behind a Fastly
    challenge (postmortem 2026-09-04).
    """
    t = str(track or "").strip().lower()
    d = str(iso_date or "")[:10]
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,24}", t):
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return None
    return f"https://raceform.co.za/horse-racing-results/{t}/{d}"


def _pool_key(pool_type) -> str:
    """Uppercase alphanumeric pool key: \"Pick 6\"/\"PICK6\"/\"pick 6\" -> PICK6."""
    return re.sub(r"[^A-Z0-9]", "", str(pool_type or "").upper())


def _raceform_page_date(page: str) -> Optional[str]:
    """The single racedate a Raceform results page actually serves, or None.

    CRITICAL: Raceform answers a no-meeting (track, date) URL with HTTP 200
    serving the NEAREST meeting instead of a 404 (verified live 2026-09:
    /vaal/2026-09-16 returned the full 2026-09-22 card). Every results /
    dividend consumer must check this against the requested date — scoring a
    ticket against the fallback day is the exact wrong-day bug this source
    exists to fix. None = ambiguous (several dates) or unreadable.
    """
    text = _rf_text(page)
    dates = set(re.findall(r'"racedate":"(\d{4}-\d{2}-\d{2})"', text))
    return dates.pop() if len(dates) == 1 else None


def _rf_float(raw) -> Optional[float]:
    """Parse a dividend amount to float (>0), None on anything unparseable.

    SA format: space thousands, comma decimals (\"1 234,50\") or plain dots
    in Raceform's JSON (\"53.500\") — mirrors _extract_pool_dividend.
    """
    try:
        val = float(str(raw).strip().replace(" ", "").replace(",", "."))
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_raceform_results(page: str, track: str, iso_date: str) -> List[Dict]:
    """Parse a Raceform archive page into ATR-shaped race dicts.

    Raceform embeds flat JSON runner objects in the page:
        {\"raceno\":1,\"finish\":2,\"horsename\":\"...\",\"racename\":\"...\", ...}
    plus meeting headers {\"raceno\":1,\"raceofftime\":\"12:15\", ...}. The
    output mirrors AtTheRacesAPI.get_results() so ``_race_runners_by_number``
    (which matches titles like \"N HH:MM ...\") and the leg scorer work
    unchanged:
        [{\"course\", \"date\", \"time\", \"title\", \"runners\": [{name, position}]}]
    Returns [] when nothing parseable — callers treat that as no-evidence
    (ticket stays PENDING), never as a result.
    """
    if not page:
        return []
    # Wrong-day guard: reject Raceform's silent nearest-meeting fallback —
    # a no-meeting URL serves another day's card with HTTP 200.
    if _raceform_page_date(page) != iso_date:
        logger.info(
            "[RACEFORM] %s %s: page serves another meeting (or none) — rejected",
            track, iso_date,
        )
        return []
    text = _rf_text(page)
    offtimes: Dict[int, str] = {}
    for m in re.finditer(r'"raceno":(\d+),"raceofftime":"(\d{2}:\d{2})"', text):
        offtimes[int(m.group(1))] = m.group(2)
    course = ""
    names: Dict[int, str] = {}
    runners: Dict[int, List[Dict]] = {}
    for m in re.finditer(r'\{[^{}]*"raceno":\d+[^{}]*\}', text):
        obj = m.group(0)
        if '"horsename"' not in obj or '"finish"' not in obj:
            continue  # meeting/race header, not a runner row
        try:
            raceno = int(re.search(r'"raceno":(\d+)', obj).group(1))
            fin = int(re.search(r'"finish":(\d+)', obj).group(1))
            nm = re.search(r'"horsename":"((?:[^"\\]|\\.)*)"', obj)
        except AttributeError:
            continue
        if not nm:
            continue
        rn = re.search(r'"racename":"((?:[^"\\]|\\.)*)"', obj)
        tk = re.search(r'"trackname":"((?:[^"\\]|\\.)*)"', obj)
        if tk and not course:
            course = tk.group(1)
        if rn and raceno not in names:
            names[raceno] = rn.group(1)
        runners.setdefault(raceno, []).append({
            "name": nm.group(1),
            "position": _finish_ordinal(fin) or "",
        })
    races: List[Dict] = []
    for raceno in sorted(runners):
        off = offtimes.get(raceno, "")
        races.append({
            "course": course or str(track or "").title(),
            "date": iso_date,
            "time": off,
            # Title MUST carry \"N HH:MM\" — _race_runners_by_number keys on it.
            "title": f"{raceno} {off} {names.get(raceno, '')}".strip(),
            "runners": runners[raceno],
        })
    return races


def _parse_raceform_dividend(
    page: str, pool_type: str, pool_legs: Optional[List[int]] = None
) -> Optional[float]:
    """Tote dividend (R per R1) for one pool from a Raceform archive page.

    Primary: embedded JSON dividend rows (verified live Sep-2026):
        {"id":..,"RacesID":137185,"bet_type":"Bipot","selections":"4,7/2,3,6/...","dividend":"53.500"}
    A page carries one row per pool PER LEG-RANGE (e.g. two Jackpots when
    both R4-7 and R5-8 are offered) — first-match used to return the wrong
    pool's dividend (2026-09-23: R4-7's R496.50 paid out on the R5-8
    ticket instead of R2,257.40). When ``pool_legs`` is given, a row is
    accepted only if its leg range (end race from the RacesID→raceno map,
    length from the selections slashes) covers exactly those legs;
    otherwise None (callers keep the ticket PENDING, never guess).
    Fallback: the rendered table row ("Bipot 4,7/2,3,6/... R53.50").
    Returns None when the pool's dividend isn't published — callers must
    keep the ticket PENDING (never fabricate a payout).
    """
    want = _pool_key(pool_type)
    if not page or not want:
        return None
    text = _rf_text(page)
    legs_wanted = {int(x) for x in pool_legs} if pool_legs else None
    rid_to_race: Dict[str, int] = {}
    if legs_wanted:
        # Per-race results blocks look like
        # "results":[{"137185":[{"results":[[[{"raceno":6,... — map each
        # block's RacesID to the first raceno inside it (blocks are
        # per-race; bracket depth varies by page).
        block_pat = re.compile(r'"(\d{5,})"\s*:\s*\[\{"results"')
        blocks = list(block_pat.finditer(text))
        for _bi, _bm in enumerate(blocks):
            _end = blocks[_bi + 1].start() if _bi + 1 < len(blocks) else len(text)
            _rm = re.search(r'"raceno"\s*:\s*(\d+)', text[_bm.end():_end])
            if _rm:
                rid_to_race.setdefault(_bm.group(1), int(_rm.group(1)))
    first: Optional[float] = None
    row_pat = (
        r'(?:\"RacesID\"\s*:\s*(\d+)\s*,\s*)?'
        r'"bet_type"\s*:\s*"([A-Za-z0-9 ]+)"\s*,\s*'
        r'"selections"\s*:\s*"[^"]*"\s*,\s*'
        r'"dividend"\s*:\s*"([\d.,]+)"'
    )
    for m in re.finditer(row_pat, text):
        if _pool_key(m.group(2)) != want:
            continue
        val = _rf_float(m.group(3))
        if val is None:
            continue
        if legs_wanted is None:
            return val  # legacy: single-pool pages, first match
        if first is None:
            first = val
        rid = m.group(1) or ""
        end = rid_to_race.get(rid)
        if end is None:
            continue  # unattributable row — never guess the leg range
        sel = re.search(
            r'"selections"\s*:\s*"([^"]*)"',
            m.group(0),
        )
        nlegs = (sel.group(1).count("/") + 1) if sel else 0
        if nlegs and set(range(end - nlegs + 1, end + 1)) == legs_wanted:
            return val
    if legs_wanted is not None:
        return None
    if first is not None:
        return first
    # Rendered-row fallback: "Bipot 4,7/2,3,6/1,4,7 R53.50" in tag-stripped text.
    stripped = re.sub(r"<[^>]+>", " ", text)
    for m in re.finditer(
        r"\b(Bipot|Place Accumulator|Pick 6|Pick 3|Jackpot)\s+[\d/,]+\s+R\s*([\d.,]+)",
        stripped,
        flags=re.IGNORECASE,
    ):
        if _pool_key(m.group(1)) == want:
            return _rf_float(m.group(2))
    return None


# --- Exotic leg-based settlement -------------------------------------------
# Pool finishing requirements per leg (SA tote rules). Unknown pools default
# to the strictest (win-only) so a ticket is never wrongly marked LOST.
def _exotic_requirement(pool_type: str) -> frozenset:
    """Positions that satisfy one leg of the pool. BIPOT pays 1st/2nd,
    place pools pay 1st/2nd/3rd, win pools (Pick 6/3, Jackpot) need 1st."""
    p = str(pool_type or "").upper()
    if "BIPOT" in p or p.strip() in ("BI", "BI1", "BI2"):
        return frozenset({"1st", "2nd"})
    if "PLACE" in p or p.strip() in ("PA",):
        return frozenset({"1st", "2nd", "3rd"})
    return frozenset({"1st"})


def _parse_exotic_ticket(bet) -> Optional[Dict]:
    """Parse an exotic ticket into pool legs + named candidates per leg.

    Primary source is the notes JSON written by record_exotic_bet
    ({pool_type, pool_legs, combinations:[{race, banker, savers[]}]}).
    Falls back to the horse field ("POOL:r1-r2-...") for legs only —
    without names a ticket cannot be evaluated (returns None).
    """
    import json as _json

    pool_type = None
    pool_legs: List[int] = []
    combos: List[Dict] = []
    try:
        notes = getattr(bet, "notes", "") or ""
        if notes.strip().startswith("{"):
            data = _json.loads(notes)
            pool_type = data.get("pool_type")
            pool_legs = [int(r) for r in (data.get("pool_legs") or [])]
            for c in (data.get("combinations") or []):
                if not isinstance(c, dict):
                    continue
                cands = []
                if c.get("banker"):
                    cands.append(str(c["banker"]))
                cands.extend(str(s) for s in (c.get("savers") or []) if s)
                if c.get("race") is not None and cands:
                    combos.append({"race": int(c["race"]), "candidates": cands})
    except Exception:
        pass
    if not pool_type:
        try:
            horse = str(getattr(bet, "horse", "") or "")
            if ":" in horse:
                pool_type, leg_str = horse.split(":", 1)
                pool_type = pool_type.strip() or None
                pool_legs = [int(x) for x in re.findall(r"\d+", leg_str)]
        except Exception:
            pass
    if not pool_type or not pool_legs:
        return None
    return {"pool_type": pool_type, "pool_legs": pool_legs, "combos": combos}


def _race_runners_by_number(races: List[Dict], race_number: int) -> Optional[List[Dict]]:
    """Find ATR result runners for a race number (title holds 'N HH:MM')."""
    for race in races or []:
        m = re.search(r"(\d+)\s+\d{2}:\d{2}", str(race.get("title", "")))
        if m and int(m.group(1)) == int(race_number):
            return race.get("runners") or []
    return None


def _extract_pool_dividend(text: str, pool_type: str) -> Optional[float]:
    """Best-effort tote dividend (Rand per R1) for a pool from results text.

    TAB result pages print lines like "JACKPOT PAYS R1 234,50". Returns the
    per-R1 Rand value, or None when no parseable dividend is present.
    """
    if not text or not pool_type:
        return None
    p = str(pool_type).upper().strip()
    aliases = {
        "BIPOT": r"BIP?OT",
        "PLACE ACCUMULATOR": r"PLACE\s*ACCUMULATOR",
        "PICK 6": r"PICK\s*6",
        "PICK 3": r"PICK\s*3",
        "JACKPOT": r"JACKPOT",
    }
    pat = aliases.get(p, re.escape(p))
    for m in re.finditer(
        rf"(?:{pat})\s*(?:PAYS|PAYOUT|POOL|DIVIDEND|WINS?)?\s*R\s*([\d\s.,]+)",
        str(text).upper(),
    ):
        raw = m.group(1).strip()
        try:
            # SA format: space thousands, comma decimals ("1 234,50").
            val = float(raw.replace(" ", "").replace(",", "."))
            if val > 0:
                return val
        except (ValueError, TypeError):
            continue
    return None


def atr_date_label(bet_date: Optional[str]) -> str:
    """Convert a BetRecord ISO date (YYYY-MM-DD) to the relative day label the
    ATR results pages understand (today/yesterday).

    Passing the raw ISO string used to build /results/2026-09-04 URLs that 404,
    silently killing the primary settlement source for every bet.
    """
    if not bet_date:
        return "yesterday"
    try:
        d = date.fromisoformat(str(bet_date)[:10])
    except (ValueError, TypeError):
        return "yesterday"
    delta = (date.today() - d).days
    if delta <= 0:
        return "today"
    return "yesterday"


def _find_race_time(
    base: str, track: str, race_number: int, bet_date: Optional[str]
) -> Optional[str]:
    """Best-effort HH:MM off-time for a race.

    Priority: (1) snapshot `bf_off_time` — the exact Betfair market startTime
    stamped by the merge, immune to TAB "12:00" placeholders; (2) the day's
    daily_scan race_time; (3) live snapshot display time. Returns None when
    unknown (no gate applied).
    """
    import json
    import os

    def _snapshot_event():
        try:
            with open(os.path.join(base, "market_snapshot_latest.json")) as f:
                snap = json.load(f)
        except Exception:
            return None
        for e in (snap.get("events") or {}).values():
            if not isinstance(e, dict):
                continue
            try:
                enum = int(e.get("raceNumber", e.get("race_number", -1)))
            except (ValueError, TypeError):
                continue
            if enum != int(race_number):
                continue
            if str(e.get("course", "")).lower() != str(track or "").lower():
                continue
            return e
        return None

    # 1. Exact Betfair off-time stamped by the merge.
    ev = _snapshot_event()
    if ev:
        off = ev.get("bf_off_time")
        if off and ":" in str(off):
            return str(off).strip()[:5]

    try:
        day = str(bet_date)[:10] if bet_date else date.today().isoformat()
    except Exception:
        day = date.today().isoformat()
    try:
        with open(os.path.join(base, f"daily_scan_{day}.json")) as f:
            scan = json.load(f)
        if isinstance(scan, dict):
            for tname, races in scan.items():
                if not isinstance(races, list):
                    continue
                if str(tname).lower() != str(track or "").lower():
                    continue
                for r in races:
                    if not isinstance(r, dict):
                        continue
                    try:
                        if int(r.get("race_number", -1)) != int(race_number):
                            continue
                    except (ValueError, TypeError):
                        continue
                    rt = r.get("race_time")
                    if rt:
                        return str(rt).strip()[:5]
    except Exception:
        pass
    # Fallback: live snapshot display time (only meaningful for today's races).
    ev = _snapshot_event()
    if ev:
        t = ev.get("t") or ev.get("st")
        if t:
            return str(t).strip()[:5]
    return None


def _scan_only_time(
    base: str, track: str, race_number: int, bet_date: Optional[str]
) -> Optional[datetime]:
    """Off-time from the bet day's daily_scan file only (date-correct).

    Used when the live snapshot carries a different meeting edition — the
    snapshot's times then say nothing about the bet, but the scan file does.
    """
    import json
    import os

    try:
        day = date.fromisoformat(str(bet_date)[:10]) if bet_date else date.today()
    except (ValueError, TypeError):
        return None
    try:
        with open(os.path.join(base, f"daily_scan_{day.isoformat()}.json")) as f:
            scan = json.load(f)
    except Exception:
        return None
    if not isinstance(scan, dict):
        return None
    for tname, races in scan.items():
        if not isinstance(races, list):
            continue
        if str(tname).lower() != str(track or "").lower():
            continue
        for r in races:
            if not isinstance(r, dict):
                continue
            try:
                if int(r.get("race_number", -1)) != int(race_number):
                    continue
            except (ValueError, TypeError):
                continue
            rt = r.get("race_time")
            if rt and ":" in str(rt):
                try:
                    h, m = int(str(rt).strip().split(":")[0]), int(str(rt).strip().split(":")[1])
                    return datetime(day.year, day.month, day.day, h, m, tzinfo=_SAST)
                except (ValueError, IndexError):
                    return None
    return None


def _iter_dates() -> List[str]:
    """Return date strings to try: today, yesterday, day-before, then bare."""
    today = date.today()
    return [
        today.strftime("%d %B %Y"),
        (today - timedelta(days=1)).strftime("%d %B %Y"),
        (today - timedelta(days=2)).strftime("%d %B %Y"),
    ]


class ResultTracker:
    """
    Automatically settles open bets by searching for race results
    via unified SearchService + direct SA scraper.
    """

    def __init__(self, bankroll_governor=None):
        self.governor = bankroll_governor
        # {(track_lower, atr_date_label): races} — one ATR scrape per
        # track/day no matter how many singles settle from it.
        self._atr_track_cache: Dict = {}

    async def _raceform_page(self, track: str, iso_date: str) -> Optional[str]:
        """Raw Raceform archive HTML for one track+date (plain HTTP — no CF
        challenge, unlike ATR/TAB). Cached per instance so the leg scorer and
        the dividend lookup share one fetch per meeting per sweep; failures
        are cached too (one attempt, no hammering). None on any failure or
        on a date outside the archive (404).
        """
        url = _raceform_url(track, iso_date)
        if not url:
            return None
        # Test instances may be built via __new__ — create the cache lazily.
        cache = getattr(self, "_raceform_cache", None)
        if cache is None:
            cache = {}
            self._raceform_cache = cache
        if url in cache:
            return cache[url]
        try:
            from core_agent.core.http_client import get_async_client
            client = get_async_client(timeout=15)
            resp = await client.get(url, headers={"Accept": "text/html"})
            page = resp.text if getattr(resp, "status_code", 0) == 200 else None
            if page and len(page) < 20_000:
                page = None  # stub/error shell, not the ~600KB results page
        except Exception as e:
            logger.debug(f"Raceform fetch failed for {url}: {e}")
            page = None
        cache[url] = page
        return page

    async def _raceform_results(self, track: str, iso_date: str) -> List[Dict]:
        """ATR-shaped results for an exact race day from the Raceform archive."""
        page = await self._raceform_page(track, iso_date)
        if not page:
            return []
        races = _parse_raceform_results(page, track, iso_date)
        logger.info("[RACEFORM] %s %s: %d races", track, iso_date, len(races))
        return races

    async def _raceform_dividend(
        self, track: str, iso_date: str, pool_type: str,
        pool_legs: Optional[List[int]] = None,
    ) -> Optional[float]:
        """Tote dividend (R per R1) for one pool from the Raceform archive.

        Refuses pages whose served racedate isn't the requested day (the
        archive silently falls back to the nearest meeting) — a dividend
        from another day must never settle this ticket. ``pool_legs``
        restricts the dividend to the row covering exactly the ticket's
        legs (a page holds one row per offered leg-range).
        """
        page = await self._raceform_page(track, iso_date)
        if not page or _raceform_page_date(page) != iso_date:
            return None
        return _parse_raceform_dividend(page, pool_type, pool_legs)

    def _monitor_cached_results(self, track: str, iso_date: str) -> List[Dict]:
        """Results the odds-monitor already scraped — the exact data the HUD
        shows (``atr_results_snapshot.json`` written by the monitor's own
        Fastly-solved ATR fetch). Reusing it means zero contention with the
        headless-Chromium throttle slot and zero CF challenge risk.

        Trusted only while its embedded timestamp is from TODAY: the file
        holds ATR's "today/yesterday" labels, which shift meaning across
        midnight — an older snapshot would silently describe different
        calendar days than its labels suggest. Never raises; [] on any miss.
        """
        try:
            from core_agent.config.paths import ATR_RESULTS_PATH
            if not os.path.exists(ATR_RESULTS_PATH):
                return []
            with open(ATR_RESULTS_PATH) as f:
                blob = json.load(f)
            if str(blob.get("timestamp") or "")[:10] != date.today().isoformat():
                return []
            cal = {
                "today": date.today().isoformat(),
                "yesterday": (date.today() - timedelta(days=1)).isoformat(),
            }
            out = []
            for race in blob.get("results") or []:
                if not isinstance(race, dict):
                    continue
                if cal.get(str(race.get("date") or "").lower()) != iso_date:
                    continue
                if str(track or "").lower() not in str(race.get("course") or "").lower():
                    continue
                out.append(race)
            return out
        except Exception as e:
            logger.debug(f"Monitor results cache read failed: {e}")
            return []

    async def _exotic_leg_races(
        self, track: str, bet_date: Optional[str]
    ) -> List[Dict]:
        """Results for the bet's OWN race day — never another day's card.

        Sources are MERGED per race (union of runners by name), not
        first-non-empty-wins: the monitor cache / ATR lists only placed
        horses and truncates 3rd+ (Sep-2026: Greyville PA sat PENDING with
        R6/R7 "unknown" because Scandalize 3rd and What A Classic 3rd were
        cut, while the full-field Raceform page was never consulted).
        1. Monitor cache — the Fastly-solved ATR data the HUD already shows;
           read while the bet is today/yesterday (ATR label semantics hold)
           and the snapshot is fresh.
        2. Raceform archive — date-addressable plain-HTTP source covering
           ~2 weeks back with full fields.
        3. ATR live — only when the merged view is still empty and
           ``atr_date_label`` maps to the bet's calendar day (delta <= 1).

        Empty list = no evidence; the caller must leave the ticket PENDING.
        """
        try:
            iso = str(bet_date)[:10] if bet_date else date.today().isoformat()
            delta = (date.today() - date.fromisoformat(iso)).days
            if delta < 0:  # future-dated input: treat as today
                iso, delta = date.today().isoformat(), 0
        except (ValueError, TypeError):
            iso, delta = date.today().isoformat(), 0
        merged: Dict[int, Dict[str, Dict]] = {}
        titles: Dict[int, str] = {}

        def _fold(races: Optional[List[Dict]]) -> None:
            for race in races or []:
                m = re.search(r"(\d+)\s+\d{2}:\d{2}", str(race.get("title", "")))
                if not m:
                    continue
                rn = int(m.group(1))
                titles.setdefault(rn, str(race.get("title", "")))
                slot = merged.setdefault(rn, {})
                for r in race.get("runners") or []:
                    key = _norm_name(str(r.get("name", "")))
                    if not key:
                        continue
                    pos = str(r.get("position", "") or "").strip()
                    prev = slot.get(key)
                    if prev is None or (not prev.get("position") and pos):
                        slot[key] = {
                            "name": str(r.get("name", "")),
                            "position": pos,
                        }

        if delta <= 1:
            _fold(self._monitor_cached_results(track, iso))
        _fold(await self._raceform_results(track, iso))
        if not merged and delta <= 1:
            try:
                from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
                _fold(await AtTheRacesAPI().get_results_for_track(
                    track, date=atr_date_label(iso)
                ))
            except Exception as e:
                logger.debug(f"Exotic ATR lookup failed for {track} {iso}: {e}")
        return [
            {
                "course": track,
                "date": iso,
                "title": titles[rn],
                "runners": list(merged[rn].values()),
            }
            for rn in sorted(merged)
        ]

    async def _atr_placing(self, track: str, race_number: int, horse: str,
                           bet_date: Optional[str] = None) -> Optional[str]:
        """Official finishing position for one single (ATR results).

        Winners are already known ("1st"); this exists for the losers —
        a LOST ticket that ran 2nd is place-pool signal, not noise.
        Cached per track/day; None on any failure (never blocks settling).
        """
        if not horse or ":" in str(horse):
            return None
        try:
            key = (str(track or "").lower(), atr_date_label(bet_date))
            if key not in self._atr_track_cache:
                from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
                atr = AtTheRacesAPI()
                self._atr_track_cache[key] = (
                    await atr.get_results_for_track(track, date=key[1])
                ) or []
            runners = _race_runners_by_number(
                self._atr_track_cache[key], int(race_number or 0)
            )
            if not runners:
                return None
            for r in runners:
                if self._fuzzy_match(str(r.get("name", "")), horse) >= 0.55:
                    return str(r.get("position", "")).strip() or None
        except Exception as e:
            logger.debug(f"ATR placing lookup failed for {horse}: {e}")
        return None

    def _fuzzy_match(self, name_a: str, name_b: str) -> float:
        a = set(_norm_name(name_a).split())
        b = set(_norm_name(name_b).split())
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        return intersection / max(len(a), len(b))

    async def _structured_placing(
        self, track: str, race_number: int, horse: str,
        bet_date: Optional[str] = None,
    ) -> Optional[tuple]:
        """Official (position, winner) for one single from merged day results.

        Same day-scoped sources the exotic scorer uses (monitor cache +
        Raceform archive, ATR live backstop) — structured proof beats the
        DDGS text search below it. (Sep-2026: nine Greyville singles sat
        PENDING 29h+ because ATR structured was throttle-starved and DDGS
        text confirmed nothing, while the results sat in the snapshot.)
        Returns (position, winner_name) with position like "1st", or None
        when the horse isn't found — never fabricate.
        """
        if not horse or ":" in str(horse):
            return None
        try:
            races = await self._exotic_leg_races(track, bet_date)
            runners = _race_runners_by_number(races, int(race_number or 0))
            if not runners:
                return None
            winner = next(
                (str(r.get("name", "")) for r in runners
                 if str(r.get("position", "")).strip() == "1st"),
                "",
            )
            for r in runners:
                if self._fuzzy_match(str(r.get("name", "")), horse) >= 0.55:
                    pos = str(r.get("position", "")).strip() or None
                    if pos:
                        return (pos, winner)
                    return None
        except Exception as e:
            logger.debug(f"Structured placing lookup failed for {horse}: {e}")
        return None

    async def _search_result(self, track: str, race_number: int, bet_date: Optional[str] = None) -> Optional[str]:
        """Search for race result text — tries ATR first, then DDGS + direct SA sites."""
        # Primary: ATR structured results (most reliable for SA racing)
        try:
            from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
            atr = AtTheRacesAPI()
            atr_date = atr_date_label(bet_date)
            winner = await atr.get_winner_for_bet(track, race_number, date=atr_date)
            if winner:
                logger.info(
                    "[RESULT] ATR winner: %s at %s R%s (odds %s)",
                    winner["horse"], track, race_number, winner.get("odds", "?"),
                )
                return f"Winner: {winner['horse']} (1st) in race {race_number} at {track}"
        except Exception as e:
            logger.debug(f"ATR lookup failed for {track} R{race_number}: {e}")

        # Fallback: DDGS with each date, then bare
        from core_agent.skills.search_service import search_racing
        for dt_str in _iter_dates():
            query = f"{track} Race {race_number} result winner {dt_str} South Africa horse racing"
            try:
                result = await search_racing(query, limit=5)
                snippets = [r.get("snippet", "") for r in result.get("results", [])]
                text = " ".join(snippets)
                if text and len(text) > 60:
                    return text
            except Exception as e:
                logger.debug(f"DDGS attempt failed ({dt_str}): {e}")

        # Bare query — no date
        try:
            query = f"{track} Race {race_number} result winner South Africa horse racing"
            result = await search_racing(query, limit=5)
            snippets = [r.get("snippet", "") for r in result.get("results", [])]
            text = " ".join(snippets)
            if text and len(text) > 60:
                return text
        except Exception as e:
            logger.debug(f"DDGS bare attempt failed: {e}")

        return await self._scrape_sa_results_direct(track, race_number)

    async def _scrape_sa_results_direct(
        self, track: str, race_number: int
    ) -> Optional[str]:
        """Direct scrape of known SA racing results pages as last resort."""
        from core_agent.core.http_client import get_async_client

        track_code_map = {
            "vaal": "XVA",
            "turffontein": "XTD",
            "fairview": "XFA",
            "scottsville": "XED",
            "kenilworth": "XCP",
            "durbanville": "XDU",
            "greyville": "XGR",
        }

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        code = track_code_map.get(track.lower())
        if not code:
            return None

        urls = [
            f"https://www.tab4racing.com/results/{yesterday}",
            f"https://www.tab.co.za/tabs/horse/all/{yesterday}/{code}",
            f"https://www.racingvitesse.co.za/results?track={code}&date={yesterday}",
            "https://raceform.co.za/cards-results",
        ]

        client = get_async_client(timeout=8)
        for url in urls:
            try:
                r = await client.get(url, headers={"Accept": "text/html"})
                if r.status_code == 200 and len(r.text) > 200:
                    cleaned = self._clean_html(r.text)
                    logger.info(
                        f"[RESULT] Direct SA fetch OK: {url} ({len(cleaned)} chars)"
                    )
                    if cleaned:
                        return cleaned
            except Exception as e:
                logger.debug(f"Direct fetch failed {url}: {e}")

        return None

    @staticmethod
    def _clean_html(html: str) -> str:
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"&[a-z]+;", " ", html)
        html = re.sub(r"\s+", " ", html).strip()
        lines = [l.strip() for l in html.split("\n") if len(l.strip()) > 30]
        return "\n".join(lines)[:3000]

    def _extract_winner(
        self, text: str, candidates: List[str]
    ) -> Tuple[Optional[str], float]:
        """
        Try to find one of the candidate horse names as the WINNER in result text.
        Returns (horse_name, confidence_score).
        Uses position indicators to avoid marking non-winners as wins.
        """
        if not text:
            return None, 0.0

        text_lower = text.lower()

        for candidate in candidates:
            cl = candidate.lower()
            patterns = [
                rf'(?:^|\s)1st\s+[^.?!]*?\b{re.escape(cl)}\b',
                rf'(?:^|\s)1\.\s*[^.?!]*?\b{re.escape(cl)}\b',
                rf'(?:^|\s)winner:?\s*[^.?!]*?\b{re.escape(cl)}\b',
                rf'(?:^|\s)won\s+by\s+[^.?!]*?\b{re.escape(cl)}\b',
                rf'\b{re.escape(cl)}\b.*?\b1st\b',
            ]
            for pat in patterns:
                if re.search(pat, text_lower):
                    return candidate, 1.0

        return None, 0.0

    def _extract_race_winner(self, text: str) -> Optional[str]:
        """Extract the confirmed winning horse name from result text if present."""
        if not text:
            return None
        patterns = [
            r'Winner:\s*([A-Za-z0-9\'\-\s]+?)(?:\s*\(1st\)|\s+in\s+race|$|\.)',
            r'(?:^|\s)1st\s+([A-Za-z0-9\'\-\s]{3,30})(?:\s*\(|\s+odds|\s+sp|$|\.|\,)',
            r'won\s+by\s+([A-Za-z0-9\'\-\s]{3,30})(?:\s*\(|\s+odds|$|\.|\,)',
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                w = m.group(1).strip()
                if w and len(w) >= 3 and not any(kw in w.lower() for kw in ["race", "track", "south africa", "result", "winner"]):
                    # Reject captures containing generic result words anywhere
                    # ("1st choice by two lengths", "the favourite won").
                    # Over-rejection only leaves a bet PENDING (safe);
                    # under-rejection fabricates LOST results (harmful).
                    words = set(w.lower().split())
                    if not words & _NON_NAME_WORDS:
                        return w
        return None

    @staticmethod
    def _race_off_datetime(
        track: str, race_number: int, bet_date: Optional[str], data_dir: Optional[str] = None
    ) -> Optional[datetime]:
        """Scheduled off-time for a race, or None if unknown.

        Prefers the Betfair-stamped exact off-time (bf_off_time) but ONLY
        when the stamped meeting date matches the bet date — otherwise the
        market belongs to a different edition of the race and its time says
        nothing about the bet. Falls back to scan/snapshot display times.
        Never raises — unknown means "no gate", not "no settle".
        """
        try:
            from core_agent.config.paths import DATA_DIR as _default_dir
        except Exception:
            _default_dir = None
        base = data_dir or (str(_default_dir) if _default_dir else None) or "./data"
        try:
            bet_day = date.fromisoformat(str(bet_date)[:10]) if bet_date else date.today()
        except (ValueError, TypeError):
            return None

        import json
        import os

        try:
            with open(os.path.join(base, "market_snapshot_latest.json")) as f:
                snap = json.load(f)
            for e in (snap.get("events") or {}).values():
                if not isinstance(e, dict):
                    continue
                try:
                    enum = int(e.get("raceNumber", e.get("race_number", -1)))
                except (ValueError, TypeError):
                    continue
                if enum != int(race_number):
                    continue
                if str(e.get("course", "")).lower() != str(track or "").lower():
                    continue
                off = e.get("bf_off_time")
                mdate = e.get("bf_event_date")
                if off and ":" in str(off) and mdate:
                    # Only trust the stamp for the bet's own meeting.
                    if str(mdate)[:10] != bet_day.isoformat():
                        return _scan_only_time(base, track, race_number, bet_date)
                    h, m = int(str(off).strip().split(":")[0]), int(str(off).strip().split(":")[1])
                    return datetime(bet_day.year, bet_day.month, bet_day.day, h, m, tzinfo=_SAST)
        except Exception:
            pass

        time_str = _find_race_time(base, track, race_number, bet_date)
        if not time_str or ":" not in time_str:
            return None
        try:
            day = date.fromisoformat(str(bet_date)[:10]) if bet_date else date.today()
        except (ValueError, TypeError):
            return None
        try:
            h, m = int(time_str.strip().split(":")[0]), int(time_str.strip().split(":")[1])
            return datetime(day.year, day.month, day.day, h, m, tzinfo=_SAST)
        except (ValueError, IndexError):
            return None

    async def _settle_exotic_ticket(self, bet, gov, brain) -> Optional[Dict]:
        from core_agent.core.correlation import tag as _tag
        """Settle one exotic pool ticket from ATR placed results.

        Leg logic (conservative — a ticket is only settled on proof):
        - each combination leg passes when the banker OR a saver finished
          inside the pool requirement (win pools: 1st; Bipot: 1st/2nd;
          Place Accumulator: 1st/2nd/3rd), fuzzy-matched like singles.
        - a combination is dead only when a leg's results are confirmed AND
          every candidate is accounted for outside the requirement. Unknown
          (missing results, unmatched names) keeps the ticket PENDING.
        - LOST when at least one combination exists and ALL are dead.
        - WON when some combination passes every leg — but only settled with
          a scraped tote dividend (settle_exotic_bet math needs real Rand).
          Without a dividend the ticket stays PENDING ("awaiting dividend").
        Returns the settled record dict, or None when left PENDING.
        """
        # ATR only serves today/yesterday result pages and the Raceform
        # archive covers ~2 weeks back — beyond EXOTIC_MAX_AGE_DAYS no source
        # can prove the ticket's own day, so scoring would mean matching
        # against some OTHER day's races. Until then honestly PENDING.
        try:
            if (_bet_age_days(getattr(bet, "date", None)) or 0) > EXOTIC_MAX_AGE_DAYS:
                return None
        except Exception:
            pass
        ticket = _parse_exotic_ticket(bet)
        if not ticket or not ticket["combos"]:
            return None
        requirement = _exotic_requirement(ticket["pool_type"])
        legs = ticket["pool_legs"]

        try:
            # Merged day-scoped sources (cache + Raceform + ATR backstop);
            # always the bet's OWN race day, never a collapsed label.
            races = await self._exotic_leg_races(
                getattr(bet, "track", ""), getattr(bet, "date", None)
            )
        except Exception as e:
            logger.debug(f"Exotic results lookup failed for {bet.bet_id}: {e}")
            return None
        if not races:
            return None

        # Gate on the last leg's off-time when known (a ticket can't be dead
        # before its final leg has run). Unknown off-time falls through to
        # evidence: only confirmed results settle anything.
        try:
            last_off = self._race_off_datetime(
                getattr(bet, "track", ""), legs[-1], getattr(bet, "date", None)
            )
        except Exception:
            last_off = None
        if last_off is not None:
            if last_off.tzinfo is None:
                last_off = last_off.replace(tzinfo=_SAST)
            if datetime.now(_SAST) < last_off + timedelta(minutes=OFF_TIME_GRACE_MINUTES):
                return None

        def leg_status(entry: Dict) -> str:
            runners = _race_runners_by_number(races, entry["race"])
            if not runners:
                return "unknown"
            best: Optional[str] = None
            matched_any = False
            for cand in entry["candidates"]:
                for r in runners:
                    if self._fuzzy_match(str(r.get("name", "")), cand) >= 0.55:
                        matched_any = True
                        pos = str(r.get("position", "")).strip()
                        if pos in requirement:
                            return "pass"
                        best = pos or best
            if matched_any:
                return "fail"  # all candidates placed outside requirement
            # No candidate found in results. For win pools a confirmed
            # different winner still kills the leg; for place pools the
            # candidate could have placed unlisted, so stay unknown.
            if requirement == frozenset({"1st"}):
                winners = [r for r in runners if str(r.get("position", "")) == "1st"]
                if winners:
                    return "fail"
            return "unknown"

        all_dead = True
        any_won_combo = False
        # Each stored entry is one leg (banker + savers); the ticket is one
        # logical combination across all legs.
        legs_state = [leg_status(e) for e in ticket["combos"]]
        if any(s == "unknown" for s in legs_state):
            return None
        if all(s == "pass" for s in legs_state):
            any_won_combo = True
            all_dead = False
        elif all(s == "fail" for s in legs_state):
            all_dead = True
        else:
            # Mixed pass/fail across legs of a single combination ticket:
            # a failed leg kills the only combination.
            all_dead = True

        if any_won_combo:
            div_text = await self._scrape_sa_results_direct(
                getattr(bet, "track", ""), legs[0]
            )
            div = _extract_pool_dividend(div_text or "", ticket["pool_type"])
            if div is None:
                # The TAB-format scrape above only sees sources that still
                # serve plain HTML (tab4racing/tab.co.za are JS shells now).
                # Raceform's archive carries every SA pool's dividend for any
                # past date — structured JSON in the page, no CF challenge.
                _bd = str(getattr(bet, "date", "") or "")[:10]
                try:
                    date.fromisoformat(_bd)
                except (ValueError, TypeError):
                    _bd = date.today().isoformat()
                try:
                    div = await self._raceform_dividend(
                        getattr(bet, "track", ""), _bd, ticket["pool_type"],
                        ticket["pool_legs"],
                    )
                except Exception as rf_err:
                    logger.debug(f"Raceform dividend lookup failed: {rf_err}")
                    div = None
            if div is None:
                # Reported (not silent): a won ticket whose dividend isn't
                # published yet stays PENDING, and the reason is visible in
                # Live Ops via the healing log + telemetry.
                msg = (
                    f"Exotic {bet.bet_id} ({ticket['pool_type']} @ "
                    f"{getattr(bet, 'track', '?')}) all {len(legs_state)} legs "
                    f"placed, awaiting tote dividend"
                )
                logger.info(msg)
                _healing_event(
                    "EXOTIC_AWAITING_DIVIDEND",
                    msg,
                    agent="ResultTracker",
                    status="WARN",
                )
                return None
            pool_return = round(div * float(getattr(bet, "stake", 0.0) or 0.0), 2)
            notes = (
                f"Auto-settled (WON all {len(legs_state)} legs, "
                f"tote dividend R{div:.2f}/R1)"
            )
            ok = gov.settle_exotic_bet(bet.bet_id, pool_return, notes) if gov else False
            won = True
        elif all_dead:
            notes = (
                f"Auto-settled (LOST — dead leg, "
                f"requirement {sorted(requirement)} not met)"
            )
            ok = gov.settle_exotic_bet(bet.bet_id, 0.0, notes) if gov else False
            won = False
            pool_return = 0.0
        else:
            return None

        if not ok:
            return None
        logger.info(
            "Auto-settled exotic: %s (%s) - %s (%s)",
            bet.horse, getattr(bet, "track", ""), "WON" if won else "LOST", notes,
        )
        try:
            _notify_exotic = True
            if gov and hasattr(gov, "mark_notified"):
                _notify_exotic = gov.mark_notified(bet.bet_id, won)
            if _notify_exotic and brain and brain.strike and brain.strike.telegram:
                await brain.strike.telegram.send_bet_result(
                    horse=bet.horse,
                    track=getattr(bet, "track", ""),
                    race_number=getattr(bet, "race_number", 0),
                    won=won,
                    stake=getattr(bet, "stake", 0.0),
                    returns=pool_return if won else 0.0,
                    profit_loss=(pool_return - float(getattr(bet, "stake", 0.0))) if won else -float(getattr(bet, "stake", 0.0)),
                    ref=_tag().strip("[]"),
                )
        except Exception as tg_err:
            logger.warning(f"{_tag()} Failed to dispatch Telegram exotic result: {tg_err}")
        return {
            "bet_id": bet.bet_id,
            "horse": bet.horse,
            "track": getattr(bet, "track", ""),
            "race_number": getattr(bet, "race_number", 0),
            "won": won,
            "notes": notes,
        }

    async def check_and_settle_open_bets(
        self, max_age_days: int = MAX_SETTLE_AGE_DAYS
    ) -> List[Dict]:
        """
        Main entry point: check all open bets and auto-settle if result found.
        Settles BOTH winning and losing bets once race results are confirmed.
        Bets older than max_age_days are DEFERRED (left PENDING for manual
        review) — settling them against recent results would usually hit the
        wrong race. Unparseable dates fail open (settled normally).
        Returns list of settled bet records.
        """
        try:
            from core_agent.core.strike_brain import brain
        except Exception as brain_import_err:
            logger.debug(f"strike_brain unavailable, using injected governor: {brain_import_err}")
            brain = None
        gov = self.governor or (brain.strike.bankroll if brain and brain.strike else None)
        if not gov:
            return []

        # Force a fresh volume view: long-lived/overlapping containers settle
        # from stale reads otherwise (Sep-2026: same bets settled+notified 2x).
        try:
            from core_agent.core.volume_sync import sync_volume

            sync_volume(max_age_secs=120)
        except Exception:
            pass

        open_bets = gov.get_open_bets()
        if not open_bets:
            return []

        from core_agent.core.correlation import bind as _bind_cid, new_id as _new_cid, tag as _tag

        _bind_cid(_new_cid("settle"))
        logger.info(f"{_tag()} settle run: {len(open_bets)} open bets")

        settled = []
        deferred: List[str] = []
        _nr_cache = {}  # lazy {date: {(course, race, horse)}} scratched sets
        for bet in open_bets:
            age = _bet_age_days(getattr(bet, "date", None))
            if age is not None and age > max_age_days:
                # Over-age bets can never be verified (ATR serves today /
                # yesterday only) — expire them out of the open book instead
                # of letting PENDINGs pile up forever. No money moves.
                try:
                    if gov and hasattr(gov, "expire_stale_bet"):
                        gov.expire_stale_bet(bet.bet_id)
                except Exception as exp_err:
                    logger.debug(f"Expire failed for {bet.bet_id}: {exp_err}")
                deferred.append(f"{bet.bet_id} ({bet.horse} @ {bet.track} R{bet.race_number}, {age}d old)")
                continue
            if _is_exotic_bet(bet):
                # Duplicate recordings (same track/date/ticket, e.g. from
                # overlapping monitor runs) — keep the earliest, cancel the
                # rest with stake refund. The recorder treats this key as one
                # ticket, so extras are never legitimate.
                try:
                    my_key = (
                        str(getattr(bet, "track", "") or "").lower(),
                        str(getattr(bet, "date", "") or ""),
                        str(getattr(bet, "horse", "") or ""),
                    )
                    older = [
                        o for o in open_bets
                        if o is not bet
                        and (
                            str(getattr(o, "track", "") or "").lower(),
                            str(getattr(o, "date", "") or ""),
                            str(getattr(o, "horse", "") or ""),
                        ) == my_key
                        and str(getattr(o, "bet_id", "")) < str(getattr(bet, "bet_id", ""))
                    ]
                    if older and gov and hasattr(gov, "cancel_pending_bet"):
                        gov.cancel_pending_bet(
                            bet.bet_id,
                            f"duplicate of {older[0].bet_id} (same ticket recorded twice)",
                        )
                        logger.info(
                            "Cancelled duplicate exotic ticket %s (kept %s)",
                            bet.bet_id, getattr(older[0], "bet_id", "?"),
                        )
                        continue
                except Exception as dupe_err:
                    logger.debug(f"Dedupe check failed for {bet.bet_id}: {dupe_err}")
                # Leg-based exotic settlement (ATR placed results + tote
                # dividends). Settles LOST on dead legs, WON with a scraped
                # dividend, else honestly leaves PENDING.
                try:
                    exotic_rec = await self._settle_exotic_ticket(bet, gov, brain)
                except Exception as exo_err:
                    logger.debug(f"Exotic settle failed for {bet.bet_id}: {exo_err}")
                    exotic_rec = None
                if exotic_rec:
                    settled.append(exotic_rec)
                continue
            # Off-time gate: never settle a race that hasn't run yet. This is
            # what fabricated this morning's LOSTs for upcoming Vaal races.
            try:
                off = self._race_off_datetime(
                    bet.track, bet.race_number, getattr(bet, "date", None)
                )
            except Exception:
                off = None
            if off is not None:
                if off.tzinfo is None:
                    off = off.replace(tzinfo=_SAST)
                if datetime.now(_SAST) < off + timedelta(minutes=OFF_TIME_GRACE_MINUTES):
                    logger.debug(
                        "Skipping %s (%s R%s): off %s, not run yet",
                        bet.bet_id, bet.track, bet.race_number, off.strftime("%H:%M"),
                    )
                    continue
            # Non-runner void: a scratched horse can neither win nor lose —
            # refund the stake (VOID) instead of fabricating a result.
            # (Sep-2026: Nkandla Gold + Got The Look scratched at Vaal while
            # the meeting stayed OPEN.) Exotics skip this: one scratched leg
            # candidate doesn't kill a multi-horse ticket.
            if not _is_exotic_bet(bet):
                try:
                    _bet_day = str(getattr(bet, "date", "") or "")[:10]
                    if _bet_day not in _nr_cache:
                        _nr_cache[_bet_day] = set()
                        _nr_data_dir = getattr(gov, "data_dir", None) or getattr(
                            getattr(brain, "strike", None), "data_dir", None)
                        if _nr_data_dir:
                            from core_agent.core.strike_tips import _snapshot_non_runners
                            _nr_cache[_bet_day] = _snapshot_non_runners(
                                _nr_data_dir, _bet_day)
                    _bt = str(getattr(bet, "track", "") or "").lower()
                    _br = int(getattr(bet, "race_number", 0) or 0)
                    _is_nr = any(
                        c == _bt and r == _br and self._fuzzy_match(h, str(bet.horse)) >= 0.55
                        for (c, r, h) in _nr_cache[_bet_day]
                    )
                except Exception as nr_err:
                    logger.debug(f"NR check skipped for {bet.bet_id}: {nr_err}")
                    _is_nr = False
                if _is_nr and gov and hasattr(gov, "cancel_pending_bet"):
                    try:
                        if gov.cancel_pending_bet(
                            bet.bet_id, f"scratched (non-runner) — stake refunded"):
                            logger.info(
                                f"{_tag()} Auto-void: {bet.horse} at {bet.track} "
                                f"R{bet.race_number} scratched (NR)")
                            settled.append({
                                "bet_id": bet.bet_id,
                                "horse": bet.horse,
                                "track": bet.track,
                                "race_number": bet.race_number,
                                "won": None,
                                "void": True,
                                "notes": "Scratched (NR) — stake refunded",
                            })
                    except Exception as void_err:
                        logger.debug(f"NR void failed for {bet.bet_id}: {void_err}")
                    continue
            # 0. Structured proof first: merged day results (monitor cache +
            # Raceform archive, ATR backstop). On a hit the DDGS text search
            # below is skipped entirely.
            settle_needed = False
            won = False
            notes = ""
            try:
                _structured = await self._structured_placing(
                    bet.track, bet.race_number, bet.horse, getattr(bet, "date", None)
                )
            except Exception as struct_err:
                logger.debug(f"Structured placing skipped for {bet.bet_id}: {struct_err}")
                _structured = None
            if _structured:
                _placed, _winner = _structured
                if _placed == "1st":
                    won = True
                    notes = "Auto-settled (WINNER confirmed, structured)"
                    _log_settled_winner(bet, bet.horse)
                else:
                    won = False
                    if _winner:
                        notes = f"Auto-settled (LOST - 1st was {_winner})"
                    else:
                        notes = f"Auto-settled (LOST - unplaced {_placed}, structured)"
                    _log_settled_winner(bet, _winner or bet.horse)
                settle_needed = True
            else:
                result_text = await self._search_result(bet.track, bet.race_number, bet_date=bet.date)
                if not result_text:
                    continue

                # 1. Text fallback — skipped when structured proof already spoke.
                if not settle_needed:
                    winner, confidence = self._extract_winner(result_text, [bet.horse])
                    settle_needed = False
                    won = False
                    notes = ""

                    if winner and confidence >= 0.55:
                        won = True
                        settle_needed = True
                        notes = f"Auto-settled (WINNER confirmed, confidence={confidence:.0%})"
                        _log_settled_winner(bet, winner)
                    else:
                        # 2. Check if a DIFFERENT winner was confirmed for this race
                        confirmed_winner = self._extract_race_winner(result_text)
                        if confirmed_winner:
                            match_score = self._fuzzy_match(confirmed_winner, bet.horse)
                            if match_score >= 0.55:
                                won = True
                                settle_needed = True
                                notes = f"Auto-settled (WINNER: {confirmed_winner}, confidence={match_score:.0%})"
                                _log_settled_winner(bet, confirmed_winner)
                            else:
                                won = False
                                settle_needed = True
                                notes = f"Auto-settled (LOST - 1st was {confirmed_winner})"
                                _log_settled_winner(bet, confirmed_winner)

            if settle_needed:
                settled_ok = False
                placed = None
                try:
                    placed = await self._atr_placing(
                        bet.track, bet.race_number, bet.horse, getattr(bet, "date", None)
                    )
                except Exception as place_err:
                    logger.debug(f"Placing lookup skipped for {bet.bet_id}: {place_err}")
                try:
                    if brain and brain.strike:
                        # settle_bet returns a status dict (never raises on a
                        # failed settle) — honor its "settled" flag instead of
                        # assuming success, or we log/notify phantom settles.
                        _res = brain.strike.settle_bet(bet.bet_id, won=won, notes=notes, placed=placed)
                        settled_ok = bool(_res.get("settled")) if isinstance(_res, dict) else bool(_res)
                except Exception as brain_err:
                    logger.debug(f"Brain settle fallback to governor: {brain_err}")

                if not settled_ok and gov:
                    settled_ok = gov.settle_bet(bet.bet_id, won=won, notes=notes, placed=placed)

                if settled_ok:
                    logger.info(
                        f"{_tag()} Auto-settled: {bet.horse} at {bet.track} R{bet.race_number} - {'WON' if won else 'LOST'} ({notes})"
                    )
                    # Confirmed values only: the local bet object may be stale
                    # when settlement ran in another process (brain path), so
                    # never read actual_return off it (Sep-2026: WON posted
                    # with R0, LOST posted with the win amount).
                    _stake = float(getattr(bet, "stake", 0.0) or 0.0)
                    _returns = float(getattr(bet, "potential_return", 0.0) or 0.0) if won else 0.0
                    profit_loss = _returns - _stake if won else -_stake
                    try:
                        _notify = True
                        if gov and hasattr(gov, "mark_notified"):
                            _notify = gov.mark_notified(bet.bet_id, won)
                        if _notify and brain and brain.strike and brain.strike.telegram:
                            await brain.strike.telegram.send_bet_result(
                                horse=bet.horse,
                                track=bet.track,
                                race_number=bet.race_number,
                                won=won,
                                stake=_stake,
                                returns=_returns,
                                profit_loss=profit_loss,
                                ref=_tag().strip("[]"),
                            )
                    except Exception as tg_err:
                        logger.warning(f"{_tag()} Failed to dispatch Telegram result alert: {tg_err}")

                    settled.append(
                        {
                            "bet_id": bet.bet_id,
                            "horse": bet.horse,
                            "track": bet.track,
                            "race_number": bet.race_number,
                            "won": won,
                            "notes": notes,
                        }
                    )

        if deferred:
            logger.info(
                "Deferred %d stale bet(s) older than %dd for manual review: %s",
                len(deferred), max_age_days, "; ".join(deferred[:10]),
            )

        # D1 memory mirror: settled outcomes so search_past_races learns from
        # real results, not just cards. Best effort — never breaks settlement.
        if settled:
            try:
                from core_agent.core.cf_push import push_insight

                _by_id = {getattr(b, "bet_id", ""): b for b in open_bets}
                for _rec in settled:
                    if _rec.get("void"):
                        continue  # NR voids refund the stake; not a result
                    _b = _by_id.get(_rec.get("bet_id", ""))
                    _stake = float(getattr(_b, "stake", 0.0) or 0.0) if _b is not None else 0.0
                    _ret = float(getattr(_b, "actual_return", 0.0) or 0.0) if _b is not None else 0.0
                    _outcome = "WON" if _rec.get("won") else "LOST"
                    _trk = str(_rec.get("track", "") or "")
                    _rn = _rec.get("race_number", 0)
                    _dt = str(getattr(_b, "date", "") or "")[:10] if _b is not None else ""
                    await push_insight(
                        doc_id=f"result-{_dt or 'nodate'}-{_trk.lower()}-r{_rn}-{_rec.get('bet_id', '')}",
                        horse=str(_rec.get("horse", "")),
                        content=(
                            f"RESULT {_outcome}: {_rec.get('horse', '')} R{_rn} @ {_trk} "
                            f"(stake R{_stake:.2f}, return R{_ret:.2f}). {_rec.get('notes', '')}"
                        ),
                        insight_type="race_result",
                        track=_trk,
                        race_number=_rn,
                        date=_dt,
                    )
            except Exception as e:
                logger.debug(f"D1 result mirror skipped: {e}")
        return settled
