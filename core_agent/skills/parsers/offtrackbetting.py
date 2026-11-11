"""Offtrackbetting.com results — the fallback when ATR is quiet.

ATR publishes most meetings, but it is silent or late for plenty of cards.
Nov-2026: ZERO Hong Kong races had ever been captured (so every HK league
pick hung until it expired, and the card never showed on the results tab),
and four UK/IRE races from Nov-10 never appeared at all.

Offtrackbetting carries the same cards — full finishing order, unplaced
runners, scratches, win/place prices and pool dividends — from a plain JSON
endpoint that answers for ANY meeting date:

    https://json.offtrackbetting.com/tracks/v2/{meetno}/{YYYYMMDD}.json

CloudFront rejects a minimal header set with "Request blocked", so the
request carries a full browser header set; with it the endpoint answers.
The site's own live API is kept as a second source:

    https://nbw78zf703.execute-api.us-west-2.amazonaws.com/today/v2?meetno={id}

Course ids come from the site's results index (a thousand-plus courses,
refreshed weekly), so a new meeting is picked up without a code change.

Conventions (mirroring the ATR parser):
  * a finished card is immutable -> cached for a day;
  * the CURRENT day's card grows race by race -> cached only briefly;
  * a failure is remembered for a short while, so one bad meeting cannot be
    re-fetched every cycle;
  * nothing raises: a miss returns [] and the caller keeps the pick pending.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("offtrackbetting")

OTB_INDEX_URL = "https://www.offtrackbetting.com/results/"
OTB_TRACK_JSON = "https://json.offtrackbetting.com/tracks/v2/{meetno}/{yyyymmdd}.json"
OTB_LIVE_API = "https://nbw78zf703.execute-api.us-west-2.amazonaws.com/today/v2?meetno={meetno}"

# A finished card never changes; the current day's card grows as races run.
_OK_TTL_SECS = 26 * 3600
# The site's edge rate-limits by egress IP (a burst of requests is answered
# with CloudFront's "Request blocked"), so the live card is refreshed
# gently — the same 20-minute cadence the Raceform backfill uses.
_LIVE_TTL_SECS = 20 * 60
_RETRY_TTL_SECS = 20 * 60
_CACHE_KEEP_DAYS = 7
_INDEX_TTL_SECS = 7 * 86400
# The site lists a thousand-plus courses; a fetch that yields a handful is
# truncated, not complete.
_MIN_INDEX_COURSES = 50

_CACHE_FILE = "otb_results_cache.json"
_INDEX_FILE = "otb_courses.json"
_TIMEOUT = 25

# CloudFront blocks a bare request; a real browser's header set gets through.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.offtrackbetting.com/",
    "Origin": "https://www.offtrackbetting.com",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "X-Requested-With": "XMLHttpRequest",
}

# The course index is a document, not an XHR: asking for JSON there returns a
# trimmed page with a handful of links instead of the full list.
_HTML_HEADERS = {
    **_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(pos: Any) -> str:
    try:
        n = int(pos)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    return _ORDINALS.get(n, f"{n}th")


def _num(value: Any) -> Optional[float]:
    """MongoDB extended JSON numbers ({'$numberDouble': '1'}) -> float."""
    if isinstance(value, dict):
        for key in ("$numberDouble", "$numberInt", "$numberLong"):
            if key in value:
                value = value[key]
                break
        else:
            return None
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(name: Any) -> str:
    """'Happy Valley (Hong Kong)' -> 'happy valley'."""
    s = re.sub(r"\([^)]*\)", " ", str(name or ""))
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def _data_dir() -> str:
    try:
        from core_agent.config.paths import DATA_DIR

        return str(DATA_DIR)
    except Exception:
        return "data"


# ── course index ─────────────────────────────────────────────────────────────


def _index_path() -> str:
    return os.path.join(_data_dir(), _INDEX_FILE)


def course_index(refresh: bool = False) -> List[Dict[str, Any]]:
    """[{id, name, base, country}] for every course OTB covers.

    Cached on the volume for a week: the index barely changes, and it is
    the only place the numeric course ids live. A cache that holds only a
    handful of courses is treated as broken (a truncated fetch once cached
    13 of a thousand) and refetched.
    """
    path = _index_path()
    if not refresh:
        try:
            raw = json.loads(Path(path).read_text())
            if isinstance(raw, dict) and raw.get("courses"):
                age = time.time() - float(raw.get("fetched_at") or 0)
                if age < _INDEX_TTL_SECS and len(raw["courses"]) >= _MIN_INDEX_COURSES:
                    return raw["courses"]
        except Exception:
            pass

    courses = _fetch_index()
    if courses:
        try:
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"fetched_at": time.time(), "courses": courses}, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception as exc:
            logger.debug("OTB course index not cached: %s", exc)
    return courses


# Country tags the site puts in the slug ("happy-valley-(hong-kong)",
# "ayr-uk", "fairview-(saf)"). A suffix that is not a country stays part of
# the name ("bathurst-harness").
_COUNTRY_CODES = {
    "aus", "uk", "ire", "fra", "saf", "rsa", "usa", "hkg", "hk", "nz", "swe",
    "tur", "jpn", "sin", "arg", "bra", "uru", "can", "zaf", "ita", "ger", "spa",
    "ind", "uae", "qat", "ksa", "kor", "tha", "mau", "per", "chi", "peru",
    "ecu", "col", "ven", "mex", "pur", "pan", "cay", "ber", "jma", "tri",
}


def _slug_parts(slug: str) -> Tuple[str, str]:
    """'happy-valley-(hong-kong)' -> ('Happy Valley', 'hong kong')."""
    raw = str(slug or "")
    raw = re.sub(r"%28", "(", raw, flags=re.I)
    raw = re.sub(r"%29", ")", raw, flags=re.I)
    country = ""
    m = re.search(r"\(([^)]+)\)\s*$", raw)
    if m:
        country = m.group(1).strip().lower()
        raw = raw[: m.start()].rstrip("-_ ")
    else:
        m = re.search(r"-([a-z]{2,3})$", raw)
        if m and m.group(1).lower() in _COUNTRY_CODES:
            country = m.group(1).lower()
            raw = raw[: m.start()]
    name = re.sub(r"[-_]+", " ", raw).strip()
    return name, country


def _fetch_index() -> List[Dict[str, Any]]:
    import httpx

    out: List[Dict[str, Any]] = []
    seen = set()
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(OTB_INDEX_URL, headers=_HTML_HEADERS)
            if resp.status_code != 200:
                logger.warning("OTB index HTTP %s", resp.status_code)
                return out
            html = resp.text or ""
    except Exception as exc:
        logger.warning("OTB index fetch failed: %s", exc)
        return out

    # The full course list is in the page's own data (a thousand-plus
    # "/results/<id>/<slug>" URLs), not only in the handful of visible
    # navigation links.
    for mid, slug, _dated in re.findall(
        r'/results/(\d+)/([a-z0-9%()\-]+?)(?:-(\d{8}))?\.html', html
    ):
        try:
            cid = int(mid)
        except (TypeError, ValueError):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        name, country = _slug_parts(slug)
        if not name:
            continue
        out.append({
            "id": cid,
            "name": name.title(),
            "base": _norm(name),
            "country": country,
        })
    logger.info("OTB course index: %d courses", len(out))
    return out


def course_id_for(track: str, region: str = "") -> Optional[int]:
    """Numeric course id for a track name, or None.

    ``region`` (the league's own tag: SA / UK / IRE / HK ...) disambiguates
    the few names that exist in more than one country.
    """
    base = _norm(track)
    if not base:
        return None
    region_key = _norm(region)
    hits = [c for c in course_index() if c.get("base") == base]
    if not hits:
        # fall back to a containment match ("happy valley" in "happy valley hk")
        hits = [c for c in course_index() if base and base in (c.get("base") or "")]
    if not hits:
        return None
    if len(hits) > 1 and region_key:
        for c in hits:
            if region_key and region_key in (c.get("country") or ""):
                return int(c["id"])
    return int(hits[0]["id"])


# ── cache ────────────────────────────────────────────────────────────────────


def _cache_path() -> str:
    return os.path.join(_data_dir(), _CACHE_FILE)


def _cache_load() -> Dict[str, Dict[str, Any]]:
    try:
        path = _cache_path()
        if Path(path).exists():
            data = json.loads(Path(path).read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _cache_store(cache: Dict[str, Dict[str, Any]]) -> None:
    try:
        now = time.time()
        cache = {
            k: v for k, v in cache.items()
            if not isinstance(v, dict) or now - float(v.get("fetched_at") or 0) < _CACHE_KEEP_DAYS * 86400
        }
        path = _cache_path()
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cache, f, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception as exc:
        logger.debug("OTB cache not stored: %s", exc)


# ── fetching ─────────────────────────────────────────────────────────────────


def fetch_meeting(meetno: int, date_iso: str) -> List[Dict[str, Any]]:
    """The confirmed card rows for one meeting and day.

    Rows use the ``confirmed_results`` shape: {date, course, race_number,
    off_time, runners:[{name, position, odds_decimal, non_runner}]}.
    [] on any miss — the caller keeps the picks pending.
    """
    day = str(date_iso or "")[:10]
    if not meetno or not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        return []
    key = f"{meetno}|{day}"
    cache = _cache_load()
    entry = cache.get(key) or {}
    age = time.time() - float(entry.get("fetched_at") or 0)
    today = time.strftime("%Y-%m-%d")
    ttl = _OK_TTL_SECS if day != today else _LIVE_TTL_SECS
    if entry.get("ok") and age < ttl:
        return list(entry.get("races") or [])
    if not entry.get("ok") and entry.get("fetched_at") and age < _RETRY_TTL_SECS:
        return []  # recently failed: do not hammer the endpoint

    payload: Optional[Dict[str, Any]] = None
    if day == today:
        # The live endpoint serves the CURRENT meeting (and answers more
        # often than the CDN does).
        payload = _fetch_json(OTB_LIVE_API.format(meetno=meetno))
    else:
        # A past day needs the dated archive. The live endpoint must NOT be
        # used as a fallback here: it serves TODAY's card, which would be
        # filed under the wrong race day.
        payload = _fetch_json(
            OTB_TRACK_JSON.format(meetno=meetno, yyyymmdd=day.replace("-", ""))
        )
    races: List[Dict[str, Any]] = []
    if payload:
        races = _parse_meeting(payload, day)
    entry = {
        "fetched_at": time.time(),
        "ok": bool(races),
        "races": races,
    }
    cache[key] = entry
    _cache_store(cache)
    if races:
        logger.info(
            "OTB meeting %s %s: %d races", meetno, day, len(races)
        )
    else:
        logger.warning("OTB meeting %s %s: no card", meetno, day)
    return races


def _fetch_json(url: str) -> Optional[Dict[str, Any]]:
    import httpx

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url, headers=_HEADERS)
            if resp.status_code != 200:
                logger.warning("OTB fetch HTTP %s %s", resp.status_code, url)
                return None
            data = resp.json()
            return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("OTB fetch failed (%s): %s", url, str(exc)[:120])
        return None


def _parse_meeting(payload: Dict[str, Any], day: str) -> List[Dict[str, Any]]:
    events = payload.get("events") or []
    if not isinstance(events, list):
        return []
    races: List[Dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        results = ev.get("results") or {}
        if not isinstance(results, dict):
            continue
        finishers = results.get("finisher") or []
        also_ran = results.get("alsoRan") or []
        scratches = results.get("scratches") or []
        if not finishers:
            continue  # the race has not run yet
        race_no = _num(ev.get("eventNo"))
        if not race_no:
            continue
        post = ev.get("postTime")
        off_time = ""
        if isinstance(post, str):
            off_time = post.split(" ")[-1][:5] if post else ""
        else:
            # The live endpoint states the post time as a UTC epoch; ATR's
            # own titles use UTC for these cards too, so the results tab
            # stays consistent (Fairview R1: 10:15 UTC = 12:15 SAST).
            num = _num(post)
            if num:
                off_time = datetime.fromtimestamp(int(num), timezone.utc).strftime("%H:%M")

        runners: List[Dict[str, Any]] = []
        for fin in finishers:
            if not isinstance(fin, dict):
                continue
            name = str(fin.get("runnerName") or "").strip()
            if not name:
                continue
            pos = _num(fin.get("finishPosition"))
            odds = _num(fin.get("winAmount"))
            runners.append({
                "number": int(_num(fin.get("programNumber")) or 0),
                "name": name,
                "position": int(pos) if pos else None,
                "odds_decimal": odds,
                "non_runner": False,
            })
        # Ran but did not place: on the card, no position.
        for name in also_ran:
            if not isinstance(name, str) or not name.strip():
                continue
            runners.append({
                "number": 0,
                "name": name.strip(),
                "position": None,
                "odds_decimal": None,
                "non_runner": False,
            })
        # Scratched: never ran (the league refunds those).
        for name in scratches:
            if not isinstance(name, str) or not name.strip():
                continue
            runners.append({
                "number": 0,
                "name": name.strip(),
                "position": None,
                "odds_decimal": None,
                "non_runner": True,
            })
        if not runners:
            continue
        races.append({
            "date": day,
            "course": "",
            "race_number": str(int(race_no)),
            "off_time": off_time,
            "runners": runners,
            "source": "otb",
        })
    return races


def get_results_for_track(track: str, date_iso: str, region: str = "") -> List[Dict[str, Any]]:
    """Confirmed card rows for a track on a date, with the course named."""
    meetno = course_id_for(track, region)
    if not meetno:
        return []
    races = fetch_meeting(meetno, date_iso)
    if not races:
        return []
    name = _display_name(track)
    for r in races:
        r["course"] = name
    return races


def _display_name(track: str) -> str:
    """The course name we already use elsewhere ('Fairview', 'Ayr')."""
    return re.sub(r"\s+", " ", str(track or "").strip())
