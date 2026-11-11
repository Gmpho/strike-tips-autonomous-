"""Structured racecard feed (phumelelaV4) — replaces the Computaform PDF parse.

Two GET endpoints, no auth, no token:

* ``GamePlayRequest`` — the meeting list for a date (SA + UK + international).
* ``getDateRaceDetailedList`` — full racecards for one ``ProgramCode``.

The payload for the racecard lives under ``result``; ``data`` is a vestigial
two-character string (``'""'``) on that endpoint, so never read it as the body.

Schema parity is verified: race and runner keysets are identical for SA and UK
(29 race keys, 114 runner keys). One parser serves both; all divergence is in
*values*, handled by the tolerant helpers below.

``odds_decimal`` of ``0.0`` means "no price published yet" — never a fabricated
starting price. Callers must treat non-positive odds as unknown.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence

from core_agent.core.http_client import get_async_client
from core_agent.skills.parsers.tab4racing import (
    ScrapedRace,
    ScrapedRunner,
    _is_number_name,
    _parse_distance_m,
)

logger = logging.getLogger("racecard-api")

PROGRAMS_URL = (
    "https://totex-vasx.4racing.com/PRODUCTS/webservice/phumelelaV4/get/"
    "GamePlayRequest/horseracing/4RACINGWEB_TAB"
)
RACECARD_URL = (
    "https://totex-col.4racing.com/PRODUCTS/webservice/phumelelaV4/get/"
    "getDateRaceDetailedList/4RACINGWEB_TAB"
)

PROGRAMS_PARAMS = {"msisdn": "0000", "game": "horseracing", "selectionType": "0"}

_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tab4racing.com/",
}

# ProgramName suffix -> jurisdiction. Suffixes are per-meeting, not per-track:
# the ProgramCode itself (XDD, CJD, NWC) carries no jurisdiction signal.
_SUFFIX_JURISDICTIONS = {
    "UK": "UK",
    "IRE": "IRE",
    "FRA": "FRA",
    "AUS": "AUS",
    "HK": "HK",
}

_BARE_SA = "SA"
_POOL = "POOL"

# Synthetic tote-pool pseudo-programs that advertise no physical meeting.
_POOL_TOKENS = {"BLITZ", "VENUE2", "QUICKMIX", "EUROPA"}
_POOL_RACE_TAG = re.compile(r"^R\d+=P\d+$", re.IGNORECASE)

_FRACTIONAL = re.compile(r"^(\d+(?:\.\d+)?)\s*[-/]\s*(\d+(?:\.\d+)?)$")
_EMPTY_SENTINELS = {"", "-", "--", "N/A", "NA", "NONE", "NULL"}


@dataclass
class Program:
    """One meeting from the GamePlayRequest option list."""

    program_code: str
    program_name: str
    venue: str
    jurisdiction: Optional[str]
    program_date: Optional[str]
    status: Optional[str] = None
    max_race: int = 0
    current_race: Optional[int] = None
    advertised_start_time: Optional[str] = None
    minutes_to_post: Optional[int] = None
    has_racecard: bool = True


def _safe_float(value) -> Optional[float]:
    """Float or None. Tolerates ``'--'`` (UK speed ratings) and spaced numbers."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(",", "")
    if text.upper() in _EMPTY_SENTINELS:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_int(value) -> Optional[int]:
    """Int or None. ``'--'``/``'X'``/``''`` all mean unknown."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if text.upper() in _EMPTY_SENTINELS:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _to_decimal(odds, tote_odds=None) -> float:
    """Fractional/colon odds to decimal, falling back to the tote decimal.

    The feed emits hyphenated fractions — including numerator < denominator
    (``'4-5'`` -> 1.8, ``'10-11'`` -> 1.909) — so a slash-only splitter is not
    enough. Returns ``0.0`` when nothing parseable: unknown, not a guess.
    """
    for raw in (odds, tote_odds):
        dec = _single_decimal(raw)
        if dec is not None:
            return dec
    return 0.0


def _single_decimal(raw) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    text = str(raw).strip().replace("$", "").upper()
    if text in _EMPTY_SENTINELS:
        return None
    if text in {"EVS", "EVENS", "EVEN"}:
        return 2.0
    match = _FRACTIONAL.match(text)
    if match:
        num, den = float(match.group(1)), float(match.group(2))
        if den:
            return round(num / den + 1.0, 4)
        return None
    value = _safe_float(text)
    if value is not None and value > 1.0:
        return round(value, 4)
    return None


def _money(value) -> Optional[float]:
    """``'120 000'`` -> 120000.0. Currency symbols/separators dropped."""
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    return float(digits) if digits else None


def _claim(value) -> Optional[str]:
    """Apprentice allowance as a bare numeric string (``'1.5000'`` -> ``'1.5'``).

    Downstream (``analyzer``, ``strike_tips``, ``betfair_sa``) expects the plain
    number, not a ``kg``-suffixed label.
    """
    allowance = _safe_float(value)
    if allowance is None or allowance <= 0:
        return None
    return f"{allowance:g}"


def _normalise_date(value=None) -> str:
    """ISO ``YYYY-MM-DD``. The feed mixes ``'T00:00:00+02:00'`` and ``' 00:00:00'``."""
    if value is None:
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10] if text else date.today().isoformat()


def _jurisdiction(program_name) -> Optional[str]:
    """``'CATTERICK_UK'`` -> ``'UK'``; ``'DURBANVILLE'`` -> ``'SA'``; pools -> ``'POOL'``."""
    name = (program_name or "").strip().upper()
    if not name:
        return None
    parts = name.split("_")
    if len(parts) >= 2 and parts[-1] in _SUFFIX_JURISDICTIONS:
        return _SUFFIX_JURISDICTIONS[parts[-1]]
    if _is_pool_program(name):
        return _POOL
    if "_" not in name:
        return _BARE_SA
    return _POOL


def _is_pool_program(program_name) -> bool:
    name = (program_name or "").strip().upper()
    if not name:
        return False
    return any(
        part in _POOL_TOKENS or _POOL_RACE_TAG.match(part)
        for part in name.split("_")
    )


def is_racecard_program(program_name) -> bool:
    """True when the program is an actual meeting with a scannable card."""
    jurisdiction = _jurisdiction(program_name)
    return bool(jurisdiction) and jurisdiction != _POOL


def _display_name(program_name) -> str:
    name = (program_name or "").strip()
    if not name:
        return ""
    parts = name.split("_")
    if len(parts) >= 2 and parts[-1].upper() in _SUFFIX_JURISDICTIONS:
        parts = parts[:-1]
    return " ".join(part for part in parts if part).replace("=", " ").strip().title()


def _race_time(value) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    tail = text.split(" ")[-1]
    if "T" in tail:
        tail = tail.split("T")[-1]
    return tail[:5]


def _track_name(race: Dict, program_name: Optional[str] = None) -> str:
    title = (race.get("Title") or "").strip()
    if title.lower().endswith(" uk"):
        title = title[: -len(" uk")].strip()
    if title:
        return title
    venue = (race.get("Venue") or "").strip()
    if venue:
        return venue.title()
    return _display_name(program_name) if program_name else ""


def _error_message(payload) -> Optional[str]:
    if not isinstance(payload, dict):
        return "non-dict payload"
    error = payload.get("error")
    if error in (0, "0", None):
        return None
    return str(payload.get("message") or error)


def _programs_payload(payload) -> Dict:
    """The program list from a GamePlayRequest body.

    The feed moved the option list from ``result`` to ``data`` (verified live
    Nov-2026) and now serves it as a LIST of meeting dicts instead of a dict
    keyed by index. Both containers are accepted and a list is normalised to a
    dict, so ``parse_programs`` iterates either shape the same way.

    A parser that only knew the old shape returned zero programs, which killed
    every live-card lookup that depends on a program code — including the
    distance backfill, and any track whose hardcoded code had rotated.
    """
    if not isinstance(payload, dict):
        return {}
    for holder in (payload.get("result"), payload.get("data")):
        if not isinstance(holder, dict):
            continue
        option_list = holder.get("option_list")
        if isinstance(option_list, dict) and option_list:
            return holder
        if isinstance(option_list, list) and option_list:
            return {"option_list": {str(i): e for i, e in enumerate(option_list)}}
    return {}


def _race_list(payload) -> List[Dict]:
    """Races live in ``result``; ``data`` is ``'""'`` on this endpoint.

    A list under either key is accepted so a future feed reshuffle does not
    silently produce an empty card.
    """
    if not isinstance(payload, dict):
        return []
    for key in ("result", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def parse_programs(payload, target_date=None) -> List[Program]:
    """Pure mapping from a GamePlayRequest body. No network."""
    if _error_message(payload):
        logger.warning("Program feed error: %s", _error_message(payload))
        return []

    option_list = _programs_payload(payload).get("option_list") or {}
    entries = option_list.values() if isinstance(option_list, dict) else option_list
    wants = _normalise_date(target_date) if target_date is not None else None

    programs: List[Program] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("ProgramCode") or "").strip().upper()
        if not code:
            continue
        program_date = (str(entry.get("ProgramDate") or "").strip()[:10]) or None
        if wants and program_date and program_date != wants:
            continue

        name = str(entry.get("ProgramName") or "").strip()
        highest = entry.get("HighestRace")
        max_race = 0
        if isinstance(highest, dict):
            max_race = _safe_int(highest.get("0")) or 0

        programs.append(
            Program(
                program_code=code,
                program_name=name,
                venue=_display_name(name),
                jurisdiction=_jurisdiction(name),
                program_date=program_date,
                status=entry.get("Status"),
                max_race=max_race,
                current_race=_safe_int(entry.get("CurrentRace")),
                advertised_start_time=entry.get("AdvertisedStartTime"),
                minutes_to_post=_safe_int(entry.get("MinutesToPost")),
                has_racecard=is_racecard_program(name),
            )
        )

    programs.sort(key=lambda p: (p.program_date or "", p.program_code))
    return programs


def parse_racecard(
    payload,
    races: Optional[Iterable[int]] = None,
    program_name: Optional[str] = None,
) -> List[ScrapedRace]:
    """Pure mapping from a getDateRaceDetailedList body. No network."""
    if _error_message(payload):
        logger.warning("Racecard feed error: %s", _error_message(payload))
        return []

    wanted = None
    if races is not None:
        wanted = {int(r) for r in races}

    jurisdiction = _jurisdiction(program_name)
    mapped: List[ScrapedRace] = []
    for race in _race_list(payload):
        scraped = _map_race(race, program_name=program_name, jurisdiction=jurisdiction)
        if scraped is None:
            continue
        if wanted is not None and scraped.race_number not in wanted:
            continue
        mapped.append(scraped)

    mapped.sort(key=lambda r: r.race_number)
    return mapped


def _map_race(
    race: Dict,
    program_name: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> Optional[ScrapedRace]:
    if not isinstance(race, dict):
        return None

    number = _safe_int(race.get("Race"))
    if number is None:
        return None

    runners = [
        runner
        for runner in (_map_runner(raw) for raw in (race.get("Runners") or []))
        if runner is not None
    ]
    if not runners:
        return None

    bet_types = [
        token.strip().upper()
        for token in str(race.get("BetTypes") or "").split(",")
        if token.strip()
    ]

    return ScrapedRace(
        track=_track_name(race, program_name),
        race_number=number,
        race_time=_race_time(race.get("AdvertisedStartTime")),
        distance=_parse_distance_m(race.get("Distance")),
        # The feed carries no going; "Good" is the consumer-compatible default
        # used by every other parser path. Never present it as observed.
        track_condition="Good",
        runners=runners,
        race_class=None,
        prize_money=_money(race.get("Stakegross")),
        bet_types=bet_types,
        jurisdiction=jurisdiction,
    )


def _map_runner(runner: Dict) -> Optional[ScrapedRunner]:
    if not isinstance(runner, dict):
        return None
    if str(runner.get("Scratched") or "").strip() == "1":
        return None

    name = str(runner.get("Name") or "").strip()
    if not name or _is_number_name(name):
        return None

    barrier = _safe_int(runner.get("Draw"))
    rating = None
    for key in ("CFRating", "MeritRating", "HCRating"):
        value = _safe_int(runner.get(key))
        if value is not None and value > 0:
            rating = value
            break

    owner = str(runner.get("Owner") or "").strip() or None

    return ScrapedRunner(
        horse_name=name,
        odds_decimal=_to_decimal(runner.get("Odds"), runner.get("Tote_Odds")),
        odds_fractional=str(runner.get("Odds") or "").strip() or None,
        jockey=str(runner.get("Jockey") or "").strip() or None,
        trainer=str(runner.get("TrainerCurrent") or "").strip() or None,
        # UK NH cards report Draw "0" — that is "no barrier", not stall zero.
        barrier=barrier if barrier and barrier > 0 else None,
        weight=_safe_float(runner.get("Weight")),
        form=str(runner.get("L3") or "").strip() or None,
        age=_safe_int(runner.get("Age")),
        sex=str(runner.get("SexLookup") or runner.get("Sex") or "").strip() or None,
        # HeadGearLookup yields "No Blinkers" noise; the raw code is the signal.
        gear=str(runner.get("Headgear") or "").strip() or None,
        days_since_run=_safe_int(runner.get("Days")),
        runner_comments=str(runner.get("RunnerComment") or "").strip() or None,
        jockey_claim=_claim(runner.get("ApprenticeAllowance")),
        official_rating=rating,
        pedigree=_pedigree(runner),
        owner=owner,
        verdict=None,
    )


def _pedigree(runner: Dict) -> Optional[str]:
    sire = str(runner.get("Sire") or "").strip()
    dam = str(runner.get("Dam") or "").strip()
    dam_sire = str(runner.get("Damby") or "").strip()
    if not sire and not dam:
        return None
    parts = [part for part in (sire, dam) if part]
    joined = " - ".join(parts)
    return f"{joined} ({dam_sire})" if dam_sire else joined


async def _close(client) -> None:
    try:
        result = client.close()
        if inspect.isawaitable(result):
            await result
    except Exception:  # pragma: no cover - transport teardown only
        pass


async def _get_json(url: str, params: Optional[Dict] = None) -> Dict:
    client = get_async_client()
    try:
        response = await client.get(url, params=params or {}, headers=_HEADERS)
        if response.status_code != 200:
            logger.warning("Racecard feed HTTP %s for %s", response.status_code, url)
            return {}
        try:
            payload = response.json()
        except Exception as exc:
            logger.warning("Racecard feed returned non-JSON: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        logger.warning("Racecard feed request failed: %s", exc)
        return {}
    finally:
        await _close(client)


async def get_programs(target_date=None) -> List[Program]:
    """Meetings for a date (default today). ProgramCode is per-meeting, so this
    is the only correct source of codes — ``tab4racing.SA_TRACKS`` is stale."""
    payload = await _get_json(PROGRAMS_URL, PROGRAMS_PARAMS)
    return parse_programs(payload, target_date=target_date)


async def get_racecard(
    program_code: str,
    program_date=None,
    races: Optional[Sequence[int]] = None,
    program_name: Optional[str] = None,
) -> List[ScrapedRace]:
    """Full card for one meeting. ``program_name`` enables jurisdiction tagging."""
    params = {
        "ProgramCode": program_code,
        "ProgramDate": _normalise_date(program_date),
    }
    if races:
        race_numbers = [int(r) for r in races]
        if len(race_numbers) == 1:
            params["Race"] = race_numbers[0]
        else:
            params["RaceList"] = ",".join(str(r) for r in race_numbers)

    payload = await _get_json(RACECARD_URL, params)
    return parse_racecard(payload, races=races, program_name=program_name)
