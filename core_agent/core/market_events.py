"""One record for "something happened in a market".

Root cause this file exists for: a price move was expressed four different
ways by four different derivations, so the surfaces disagreed and none of
them knew whether the move concerned the user's own pick.

- ``Logs``            read ``alert_history.json`` (the alert engine's own log)
- ``Market Movers``   read ATR's page, 45 minutes behind and behind a challenge
- ``Live Ops``        re-derived its own odds lines
- ``Telegram``        read ``odds_journey.json`` and formatted its own rows

Every one of those now reads HERE instead. One record, one writer per
source, one store::

    data/market_events.jsonl   append-only, pruned by age

Sources and what they mean:

===============  ===========================================================
``snapshot``     Our own 5-minute market snapshot, diffed per runner. This
                 is the **primary** source: fresher than ATR and not behind
                 a challenge wall.
``alert_engine`` One of the engine's ``ODDS_DROP`` alerts, normalised. It is
                 an *alert* (a rule fired), not an observation of a move.
``atr``          ATR's Market Movers page. Demoted to a **fallback** for
                 meetings we do not scrape, always tagged, always carrying
                 its age so no surface can present it as fresher than it is.
===============  ===========================================================

A move is only ever recorded when the price changed **within the same book**,
the change exceeds the threshold, and neither side was a placeholder — a
market *opening* (SP or ``0`` becoming a real price) is not a move.

Nothing here raises. Every entry point is called from a cron cycle that must
survive a bad feed.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from core_agent.config.paths import DATA_DIR

logger = logging.getLogger("market-events")

MARKET_EVENTS_PATH = DATA_DIR / "market_events.jsonl"
PRICE_BASELINE_PATH = DATA_DIR / "market_price_baseline.json"

# --- Event kinds ----------------------------------------------------------
KIND_PRICE_MOVE = "price_move"
KIND_ODDS_DROP = "odds_drop"

# --- Thresholds -----------------------------------------------------------
# Mirrors the alert engine's own "did anything happen?" test so a move that
# the Logs view calls noise cannot become a Movers card, and vice versa.
MIN_MOVE_PCT = 5.0
MIN_MOVE_ABS = 0.5
# A price that moves 0.02 on a 2.0 shot is 1% and 0.02 — below both.
STEAMER_PCT = 30.0  # matches the HUD's isSteamer (price collapsed >= 30%)

# --- Debounce -------------------------------------------------------------
# One busy race must not flood every surface. Within a poll a runner can
# only produce one event; across polls the same runner is quiet for this
# long; and a race can only contribute this many events per poll.
RUNNER_COOLDOWN_MINUTES = 10
MAX_EVENTS_PER_RACE = 3

# --- Retention ------------------------------------------------------------
MAX_AGE_HOURS = 26  # a full race day plus slack
BASELINE_MAX_AGE_HOURS = 26


def _now() -> datetime:
    return datetime.now()


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
def course_key(course: Any) -> str:
    """"Greyville (RSA)" -> "greyville", so picks and cards line up."""
    return re.sub(r"\([^)]*\)", " ", str(course or "")).strip().lower()


def runner_key(name: Any) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def _digest(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def move_id(course: Any, race_number: Any, runner: Any,
            prev: float, price: float) -> str:
    """Stable id for one specific price transition.

    The same transition observed twice — by two sources, or by the same
    source twice — produces the same id, so the store can hold "one move,
    one record" by simple id dedupe rather than by timestamp guessing.
    """
    return "pm_" + _digest(
        KIND_PRICE_MOVE,
        course_key(course),
        race_number,
        runner_key(runner),
        round(float(prev), 3),
        round(float(price), 3),
    )


# --------------------------------------------------------------------------
# Reading the market
# --------------------------------------------------------------------------
def real_price(value: Any) -> Optional[float]:
    """A usable decimal price, or None.

    ``0``, ``1``, ``"SP"``, ``"n/a"``, ``None`` and junk are all *absence* of
    a price, never a price of zero. This is the same rule the HUD's
    ``marketStatus`` applies, kept in step deliberately: a card that says
    "no prices yet" must not also produce a mover.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        price = float(value)
    else:
        text = str(value).strip()
        if not text or text.upper() in ("SP", "N/A", "NA", "-", "TBD"):
            return None
        try:
            price = float(text)
        except (TypeError, ValueError):
            return None
    return price if price > 1.0 else None


def _book_of(runner: Dict[str, Any]) -> str:
    """Which book priced this runner.

    Betway is currently the only source that carries prices at all —
    Betfair SA is a form feed (ratings, pedigree, days since run, owner)
    with no price field anywhere. The book is still tracked explicitly so
    a second price source can be added without every stored move becoming
    suspect, and so "same book" is a rule the code states rather than a
    fact it silently relies on.
    """
    return str(runner.get("book") or runner.get("source_book") or "betway")


def is_move(prev: Optional[float], price: Optional[float]) -> bool:
    """Did a price actually move, or did a market merely open?

    Both sides must be real prices. SP -> 6.5 is a market opening, not a
    move, and reporting it as one would put a fake "huge drift" on the card
    every time a meeting starts being quoted.
    """
    if prev is None or price is None:
        return False
    if prev <= 1.0 or price <= 1.0:
        return False
    change_pct = abs(price - prev) / prev * 100.0
    change_abs = abs(price - prev)
    return change_pct >= MIN_MOVE_PCT or change_abs >= MIN_MOVE_ABS


def move_pct(prev: float, price: float) -> float:
    """Percent move where **positive means the price shortened** (steamer).

    Same sign convention as the Telegram digester's ``_move_pct``
    (``(open - latest) / open``), so a row that says STEAMER there and a
    badge that says shortened here can never point opposite ways.
    """
    if not prev:
        return 0.0
    return round((prev - price) / prev * 100.0, 1)


def _severity(pct: float) -> str:
    if pct >= STEAMER_PCT:
        return "steamer"
    if pct <= -STEAMER_PCT:
        return "drifter"
    return "move"


# --------------------------------------------------------------------------
# The user's own picks
# --------------------------------------------------------------------------
def load_pick_index(data_dir: Optional[str] = None,
                    date: Optional[str] = None) -> List[Dict[str, Any]]:
    """The user's picks for ``date`` (default: today), for event joins.

    Returns a list rather than a dict because the join is fuzzy on the
    horse name (``names_match``), which a dict lookup cannot express.
    """
    path = os.path.join(str(data_dir or DATA_DIR), "league_picks.jsonl")
    picked: List[Dict[str, Any]] = []
    try:
        wanted = date or _now().date().isoformat()
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                row_date = str(
                    row.get("date")
                    or str(row.get("off_iso") or "")[:10]
                )[:10]
                if row_date and row_date != wanted:
                    continue
                picked.append(row)
    except FileNotFoundError:
        return []
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Could not read league picks: %s", exc)
        return []
    return picked


def _pick_for(picks: Iterable[Dict[str, Any]], course: Any,
              race_number: Any, runner: Any) -> Optional[Dict[str, Any]]:
    """The user's pick on this runner, if they hold one."""
    try:
        from core_agent.skills.league.settlement import names_match
    except Exception:  # pragma: no cover - defensive
        return None

    for row in picks:
        try:
            if course_key(row.get("course")) != course_key(course):
                continue
            if str(row.get("race_number")) != str(race_number):
                continue
            if names_match(row.get("runner_name"), runner):
                return row
        except Exception:
            continue
    return None


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------
def _events_path(path: Optional[Any] = None) -> Any:
    return path or MARKET_EVENTS_PATH


def read_events(limit: Optional[int] = None,
                since_hours: Optional[float] = None,
                kinds: Optional[Iterable[str]] = None,
                sources: Optional[Iterable[str]] = None,
                path: Optional[Any] = None,
                now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Read the store, newest first. Never raises.

    ``now`` is passed by callers that compute an age (the debounce window)
    so the cutoff is measured against the cycle's clock rather than the
    wall clock — a diff backfilled or replayed must not silently think
    every recent event is still inside its cooldown.
    """
    want_kinds = set(kinds) if kinds else None
    want_sources = set(sources) if sources else None
    cutoff = None
    if since_hours is not None:
        cutoff = (now or _now()) - timedelta(hours=since_hours)

    rows: List[Dict[str, Any]] = []
    try:
        with open(_events_path(path)) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if want_kinds and row.get("kind") not in want_kinds:
                    continue
                if want_sources and row.get("source") not in want_sources:
                    continue
                if cutoff is not None:
                    ts = _parse_ts(row.get("ts"))
                    if ts is None or ts < cutoff:
                        continue
                rows.append(row)
    except FileNotFoundError:
        return []
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Could not read market events: %s", exc)
        return []

    rows.sort(key=lambda r: str(r.get("ts") or ""), reverse=True)
    if limit is not None:
        rows = rows[:limit]
    return rows


def _parse_ts(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _prune(rows: List[Dict[str, Any]], now: Optional[datetime] = None,
           max_age_hours: float = MAX_AGE_HOURS) -> List[Dict[str, Any]]:
    """Drop events older than the retention window (and undateable ones)."""
    now = now or _now()
    cutoff = now - timedelta(hours=max_age_hours)
    kept = []
    for row in rows:
        ts = _parse_ts(row.get("ts"))
        if ts is not None and ts >= cutoff:
            kept.append(row)
    return kept


def append_events(events: Iterable[Dict[str, Any]],
                  path: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Merge events into the store: dedupe by id, prune by age, write atomically.

    Returns the events actually new to the store (callers log that count).
    A rewrite rather than a blind append, because the store must be pruned
    on the same cadence it is written or it grows without bound; the write
    goes to a temp file and is ``os.replace``d so a crash can never leave a
    half-written store behind.
    """
    incoming = [e for e in (events or []) if isinstance(e, dict) and e.get("id")]
    if not incoming:
        return []

    target = _events_path(path)
    existing = read_events(path=target)
    known_ids = {str(row.get("id")) for row in existing}

    fresh: List[Dict[str, Any]] = []
    for event in incoming:
        eid = str(event.get("id"))
        if eid in known_ids:
            continue
        known_ids.add(eid)
        fresh.append(event)

    if not fresh:
        return []

    merged = _prune(existing + fresh)
    merged.sort(key=lambda r: str(r.get("ts") or ""))
    try:
        tmp = f"{target}.tmp"
        os.makedirs(os.path.dirname(str(target)) or ".", exist_ok=True)
        with open(tmp, "w") as f:
            for row in merged:
                f.write(json.dumps(row, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not persist market events: %s", exc)
        return []

    return fresh


# --------------------------------------------------------------------------
# Baseline (the previous price of every runner we have seen)
# --------------------------------------------------------------------------
def _baseline_path(path: Optional[Any] = None) -> Any:
    return path or PRICE_BASELINE_PATH


def _load_baseline(path: Optional[Any] = None) -> Dict[str, Any]:
    try:
        with open(_baseline_path(path)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_baseline(baseline: Dict[str, Any], path: Optional[Any] = None) -> None:
    """Persist the last-known price per runner, pruned by age. Never raises."""
    try:
        cutoff = _now() - timedelta(hours=BASELINE_MAX_AGE_HOURS)
        kept = {
            k: v for k, v in baseline.items()
            if isinstance(v, dict) and (_parse_ts(v.get("ts")) or cutoff) >= cutoff
        }
        target = _baseline_path(path)
        tmp = f"{target}.tmp"
        os.makedirs(os.path.dirname(str(target)) or ".", exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(kept, f, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Could not persist price baseline: %s", exc)


def _baseline_key(date: str, event: Dict[str, Any], runner: Dict[str, Any],
                  book: str) -> str:
    return "|".join([
        date,
        course_key(event.get("course")),
        str(event.get("raceNumber") or ""),
        runner_key(runner.get("name")),
        book,
    ])


# --------------------------------------------------------------------------
# Snapshot diffing — the primary source
# --------------------------------------------------------------------------
def diff_snapshot(state: Dict[str, Any],
                  picks: Optional[List[Dict[str, Any]]] = None,
                  now: Optional[datetime] = None,
                  baseline_path: Optional[Any] = None,
                  events_path: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Diff a market snapshot against the last seen prices.

    One pass, per runner:

    - compare against the same runner **in the same book** (a book switch is
      not a move);
    - skip anything that is not a real price on both sides (an opening);
    - skip changes under threshold;
    - collapse to one event per runner, cap the race, honour the cooldown;
    - refresh the baseline with everything seen, moved or not.

    Returns the events written. Never raises.
    """
    now = now or _now()
    try:
        events_blob = (state or {}).get("events") or {}
        if not isinstance(events_blob, dict):
            return []
        snapshot_date = str((state or {}).get("timestamp") or now.isoformat())[:10]
        if picks is None:
            picks = load_pick_index(date=snapshot_date)

        baseline = _load_baseline(baseline_path)
        recent = read_events(since_hours=RUNNER_COOLDOWN_MINUTES / 60.0,
                             kinds=[KIND_PRICE_MOVE], path=events_path,
                             now=now)
        cooling = {
            str(r.get("cooldown_key") or "")
            for r in recent if r.get("cooldown_key")
        }

        candidates: Dict[str, Dict[str, Any]] = {}
        per_race: Dict[str, List[Dict[str, Any]]] = {}

        for race_id, event in events_blob.items():
            if not isinstance(event, dict) or event.get("isFinished"):
                continue
            course = event.get("course")
            race_number = event.get("raceNumber") or event.get("race_number")
            if not course or race_number is None:
                continue
            for runner in event.get("runners") or []:
                if not isinstance(runner, dict) or runner.get("non_runner"):
                    continue
                name = runner.get("name")
                if not name:
                    continue
                book = _book_of(runner)
                price = real_price(runner.get("odds"))
                key = _baseline_key(snapshot_date, event, runner, book)
                prev_entry = baseline.get(key) or {}
                prev = real_price(prev_entry.get("price"))

                # Refresh the baseline whatever happens next: a market we
                # have just started quoting must be remembered at that
                # price, or its next quote would look like an opening again.
                if price is not None:
                    baseline[key] = {"price": price, "ts": now.isoformat()}

                if not is_move(prev, price):
                    continue
                if key in cooling:
                    continue

                pct = move_pct(prev, price)
                uid = move_id(course, race_number, name, prev, price)
                candidates[uid] = {
                    "id": uid,
                    "cooldown_key": key,
                    "ts": now.isoformat(),
                    "kind": KIND_PRICE_MOVE,
                    "race": {
                        "id": str(event.get("id") or race_id),
                        "course": course,
                        "race_number": race_number,
                        "off": event.get("t"),
                        "off_local": event.get("bf_off_time"),
                        "date": snapshot_date,
                    },
                    "runner": {
                        "name": name,
                        "number": runner.get("number"),
                    },
                    "book": book,
                    "prev": prev,
                    "price": price,
                    "move_pct": pct,
                    "direction": "shortened" if pct > 0 else "drifted",
                    "severity": _severity(pct),
                    "source": "snapshot",
                }
                origin = _pick_for(picks, course, race_number, name)
                if origin is not None:
                    candidates[uid]["is_user_pick"] = True
                    candidates[uid]["pick"] = {
                        "handle": origin.get("handle"),
                        "runner_name": origin.get("runner_name"),
                        "pick_odds": origin.get("pick_odds"),
                    }

                race_cap = f"{course_key(course)}|{race_number}"
                per_race.setdefault(race_cap, []).append(candidates[uid])

        # One busy race must not flood every surface: keep its biggest moves.
        kept: List[Dict[str, Any]] = []
        for rows in per_race.values():
            rows.sort(key=lambda r: abs(float(r.get("move_pct") or 0)), reverse=True)
            kept.extend(rows[:MAX_EVENTS_PER_RACE])

        _save_baseline(baseline, baseline_path)
        return append_events(kept, path=events_path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Snapshot diff skipped: %s", exc)
        return []


# --------------------------------------------------------------------------
# Other sources
# --------------------------------------------------------------------------
def from_alert(msg: Dict[str, Any],
               picks: Optional[List[Dict[str, Any]]] = None,
               now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Normalise the alert engine's ODDS_DROP message into a canonical record.

    This is an *alert*, not an observed move, so it is recorded as its own
    kind. It carries the odds the alert fired on, and the open price the
    engine's journey store remembers, so a reader can still see the trail.
    """
    if not isinstance(msg, dict):
        return None
    now = now or _now()
    try:
        alert_type = str(msg.get("type") or "")
        if alert_type not in ("odds_drop", "odds_rise", "threshold"):
            return None
        course = msg.get("course")
        horse = msg.get("horse")
        price = real_price(msg.get("odds"))
        if not course or not horse or price is None:
            return None
        race_number = msg.get("race")
        journey = msg.get("journey") or {}
        opening = real_price(journey.get("open")) or price
        pct = move_pct(opening, price)

        event = {
            "id": "od_" + _digest("odds_drop", course_key(course),
                                  race_number, runner_key(horse),
                                  round(opening, 3), round(price, 3)),
            "ts": str(msg.get("timestamp") or now.isoformat()),
            "kind": KIND_ODDS_DROP,
            "race": {
                "id": None,
                "course": course,
                "race_number": race_number,
                "off": msg.get("off"),
                "off_local": msg.get("off"),
                "date": str(msg.get("timestamp") or now.isoformat())[:10],
            },
            "runner": {"name": horse, "number": None},
            "book": "betway",
            "prev": opening,
            "price": price,
            "move_pct": pct,
            "direction": "shortened" if pct > 0 else "drifted",
            "severity": _severity(pct),
            "source": "alert_engine",
            "alert_type": alert_type,
        }
        if msg.get("enrich"):
            event["enrich"] = msg["enrich"]
        if picks is None:
            picks = load_pick_index(date=event["race"]["date"])
        if _pick_for(picks, course, race_number, horse) is not None:
            event["is_user_pick"] = True
        return event
    except Exception as exc:  # pragma: no cover - defensive
        return None


def record_alert(msg: Dict[str, Any],
                 events_path: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Persist one alert-engine message as a canonical event."""
    event = from_alert(msg)
    if event is None:
        return []
    return append_events([event], path=events_path)


def from_atr(movers: Iterable[Dict[str, Any]],
             fetched_at: Optional[Any] = None,
             now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Tag ATR's movers as the fallback they now are, with their age.

    ATR's page refreshes on a 45-minute gate and sits behind a challenge
    wall, so an ATR row is never as fresh as it looks. Every event carries
    ``source`` and ``age_secs`` so a surface can say so instead of implying
    a 45-minute-old price is live.
    """
    now = now or _now()
    fetched = _parse_ts(fetched_at) if fetched_at else None
    age_secs = int((now - fetched).total_seconds()) if fetched else None

    out: List[Dict[str, Any]] = []
    for row in movers or []:
        if not isinstance(row, dict):
            continue
        horse = row.get("horse") or row.get("name")
        course = row.get("course")
        if not horse or not course:
            continue
        price = real_price(row.get("current_odds"))
        opening = real_price(row.get("first_show"))
        pct = move_pct(opening, price) if (opening and price) else None
        out.append({
            "id": "atr_" + _digest(
                "atr", course_key(course), row.get("time"), runner_key(horse),
                opening, price, row.get("movement"),
            ),
            "ts": (fetched or now).isoformat(),
            "kind": KIND_PRICE_MOVE,
            "race": {
                "id": None,
                "course": course,
                "race_number": None,
                "off": row.get("time"),
                "off_local": row.get("time"),
                "date": (fetched or now).date().isoformat(),
            },
            "runner": {"name": horse, "number": None},
            "book": "atr",
            "prev": opening,
            "price": price,
            "move_pct": pct if pct is not None else row.get("movement"),
            "direction": ("shortened" if (pct or 0) > 0
                          else "drifted" if (pct or 0) < 0 else "stable"),
            "severity": _severity(pct or 0.0),
            "source": "atr",
            "age_secs": age_secs,
        })
    return out


# --------------------------------------------------------------------------
# Serving
# --------------------------------------------------------------------------
def _utc_wall_to_sast(wall: Any) -> Any:
    """HH:MM UTC wall -> HH:MM South African clock face, wrapped at midnight.

    The snapshot stores Betway's ``t`` as a UTC wall-clock while Betfair's
    ``offTime``/``bf_off_time`` is already SAST, so a meeting that Betfair
    does not carry has no local time to read and would otherwise render two
    hours early. South Africa is a fixed UTC+2 with no daylight saving.
    """
    if not isinstance(wall, str) or ":" not in wall:
        return wall
    try:
        h, m = wall.strip().split(":")[:2]
        total = (int(h) * 60 + int(m) + 120) % (24 * 60)
        return f"{total // 60:02d}:{total % 60:02d}"
    except (ValueError, TypeError):
        return wall


def _display_off(race: Dict[str, Any]) -> Any:
    """The race's off-time as a clock face a punter recognises."""
    local = race.get("off_local")
    if local:
        return local
    return _utc_wall_to_sast(race.get("off"))


def _move_label(pct: Any) -> str:
    """A movement string that cannot be misread, for the HUD's fallback path.

    The view derives direction from prev/current whenever both are numbers,
    so this is only used when they are not — and a bare "+18%" would then be
    interpreted by a sign convention that differs from ``move_pct``
    (positive here means the price shortened). Words, not signs.
    """
    if not isinstance(pct, (int, float)):
        return ""
    if pct > 0:
        return f"Shortened {abs(pct):.1f}%"
    if pct < 0:
        return f"Drifted {abs(pct):.1f}%"
    return "Stable"


def movers_for_hud(limit: int = 60,
                   atr_blob: Optional[Dict[str, Any]] = None,
                   events_path: Optional[Any] = None) -> List[Dict[str, Any]]:
    """The Movers feed: our own events first, ATR as tagged fallback.

    Shape is the HUD's existing ``MarketMover`` (horse / course / time /
    current_odds / first_show / movement) so the view keeps working while
    the data underneath becomes canonical. Extra keys (``id``, ``source``,
    ``age_secs``, ``move_pct``, ``direction``, ``severity``, ``is_user_pick``)
    are additive — the view may use them to show provenance.
    """
    rows: List[Dict[str, Any]] = []
    ours = read_events(limit=limit, kinds=[KIND_PRICE_MOVE],
                       sources=["snapshot"], path=events_path)
    for event in ours:
        rows.append({
            "id": event.get("id"),
            "horse": (event.get("runner") or {}).get("name"),
            "course": (event.get("race") or {}).get("course"),
            "time": _display_off(event.get("race") or {}),
            "current_odds": event.get("price"),
            "first_show": event.get("prev"),
            # Human-readable rather than a bare signed number: the view
            # derives direction from prev/current when both are present, so
            # this string only matters as a fallback — and as a fallback it
            # must not be ambiguous about which way the price went.
            "movement": _move_label(event.get("move_pct")),
            "move_pct": event.get("move_pct"),
            "direction": event.get("direction"),
            "severity": event.get("severity"),
            "source": "snapshot",
            "age_secs": _age_secs(event.get("ts")),
            "timestamp": event.get("ts"),
            "is_user_pick": bool(event.get("is_user_pick")),
            "race_number": (event.get("race") or {}).get("race_number"),
        })

    # ATR fills in only meetings our snapshot does not cover — it must never
    # outrank an event we observed ourselves.
    covered = {course_key(r.get("course")) for r in rows}
    if isinstance(atr_blob, dict):
        atr_rows = from_atr(atr_blob.get("movers") or [],
                            fetched_at=atr_blob.get("timestamp"))
        for event in atr_rows:
            if course_key((event.get("race") or {}).get("course")) in covered:
                continue
            rows.append({
                "id": event.get("id"),
                "horse": (event.get("runner") or {}).get("name"),
                "course": (event.get("race") or {}).get("course"),
                "time": (event.get("race") or {}).get("off"),
                "current_odds": event.get("price"),
                "first_show": event.get("prev"),
                "movement": (
                    _move_label(event.get("move_pct"))
                    if isinstance(event.get("move_pct"), (int, float))
                    else event.get("move_pct")
                ),
                "move_pct": event.get("move_pct"),
                "direction": event.get("direction"),
                "severity": event.get("severity"),
                "source": "atr",
                "age_secs": event.get("age_secs"),
                "timestamp": event.get("ts"),
                "is_user_pick": False,
            })

    rows.sort(key=lambda r: (r.get("source") != "snapshot",
                             -(r.get("move_pct") or 0)
                             if isinstance(r.get("move_pct"), (int, float)) else 0))
    return rows[:limit]


def alerts_for_hud(limit: int = 20,
                   events_path: Optional[Any] = None) -> List[Dict[str, Any]]:
    """The Logs audit trail: alerts, read from the canonical store.

    Keeps the shape the HUD already understands (``type``, ``horse``,
    ``course``, ``odds``, ``timestamp``, ``race``) so the timeline view and
    its bet cross-links keep working.
    """
    rows = read_events(limit=limit, kinds=[KIND_ODDS_DROP], path=events_path)
    out = []
    for event in rows:
        race = event.get("race") or {}
        out.append({
            "alert_id": event.get("id"),
            "type": event.get("alert_type") or "odds_drop",
            "course": race.get("course"),
            "horse": (event.get("runner") or {}).get("name"),
            "odds": event.get("price"),
            "timestamp": event.get("ts"),
            "race": race.get("race_number"),
            "off": race.get("off"),
            "source": event.get("source"),
            "is_user_pick": bool(event.get("is_user_pick")),
        })
    return out


def _age_secs(ts: Any) -> Optional[int]:
    parsed = _parse_ts(ts)
    if parsed is None:
        return None
    return int((_now() - parsed).total_seconds())
