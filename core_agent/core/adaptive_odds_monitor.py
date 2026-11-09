import asyncio
import difflib
import glob
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from core_agent.config.paths import MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR, ATR_RESULTS_PATH, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH, DATA_DIR
from core_agent.core.alert_engine import AlertEngine
from core_agent.core.alert_digester import AlertDigester
from core_agent.skills.parsers.betway_api import BetwayAPI
try:
    from core_agent.skills.swarm_researcher import (
        enrich_snapshot_with_insights,
        run_swarm_loop,
    )
    _HAS_SWARM = True
except ImportError:
    _HAS_SWARM = False

    def enrich_snapshot_with_insights(state):  # no-op fallback
        return None

    async def run_swarm_loop(interval=600):
        return None
try:
    from core_agent.skills.parsers.racing_odds_api import RacingOddsAPI, _normalise
    _HAS_RACING_ODDS = True
except ImportError:
    _HAS_RACING_ODDS = False

    def _normalise(name: str) -> str:
        import re
        return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

    class RacingOddsAPI:
        async def get_snapshot_format(self, target_date=None):
            return {"events": {}, "count": 0}

try:
    from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
    _HAS_ATR = True
except ImportError:
    _HAS_ATR = False

    class AtTheRacesAPI:
        async def get_results(self, date): return []
        async def get_market_movers(self): return []
        async def get_predictor(self): return []
try:
    from core_agent.skills.parsers.betfair_sa import BetfairSA, _normalise as _bf_normalise
    _HAS_BETFAIR_SA = True
except ImportError:
    _HAS_BETFAIR_SA = False

    def _bf_normalise(name: str) -> str:
        return "".join(c for c in name.lower() if c.isalnum())

    class BetfairSA:
        async def get_form_format(self) -> dict:
            return {"events": {}, "count": 0}
from core_agent.core.intelligence_cache_manager import IntelligenceCacheManager

HEALING_EVENTS_PATH = os.path.join("data", "healing_events.json")


def _norm_time(t: str) -> str:
    """Normalise race time to HH:MM format."""
    return t.replace("-", ":").replace(".", ":").strip()


def _parse_race_off_time(t_str: str, race_date: datetime = None) -> Optional[datetime]:
    """Parse HH:MM race time into a datetime for off-time comparison.

    Rolls far-future times back to yesterday: a persisted "23:44" seen at
    00:14 belongs to yesterday's card, not tonight's — without this, zombie
    events linger ~24h (the persisted-zombie window after midnight).
    """
    if not t_str or ":" not in t_str:
        return None
    try:
        parts = t_str.strip().split(":")
        h, m = int(parts[0]), int(parts[1])
        base = race_date or datetime.now()
        parsed = base.replace(hour=h, minute=m, second=0, microsecond=0)
        if (parsed - base).total_seconds() > 18 * 3600:
            parsed -= timedelta(days=1)
        return parsed
    except (ValueError, IndexError):
        return None


# Races whose off-time cannot be parsed from any source are dropped once they
# have been observed (first_seen stamp) for longer than this — prevents
# unfinished/unparseable races from hoarding the dashboard all day.
UNPARSEABLE_RACE_TTL_SECS = 6 * 60 * 60

# Betfair form cache manager: a market stays in the rolling cache while its
# race is upcoming and is dropped once its off-time passes (grace mirrors
# ``betfair_sa._EXPIRED_MARKET_GRACE_SECS``); an entry that stops refreshing
# entirely ages out after BF_ENTRY_TTL_SECS.
BF_GHOST_GRACE_SECS = 5 * 60
BF_ENTRY_TTL_SECS = 6 * 60 * 60

# Gap between the previous snapshot's timestamp and the current cycle beyond
# which a MONITOR_STALL healing event is recorded (cron stalled or missed).
MONITOR_STALL_SECS = 15 * 60

# Deadline for the whole upstream fetch phase (Betway + Racing-Odds +
# Betfair). Oct-2026 odds freeze: ``state = await bw_task`` had no deadline and
# curl_cffi could keep one socket open forever, so the cycle blocked with no
# snapshot write until Modal killed the container at 900s on every tick.
# Must stay below the 900s cron timeout to leave room for the write, the ATR
# refresh and the alert flush that follow the fetch.
SOURCE_PHASE_TIMEOUT_SECS = 480


async def _collect_sources(
    pending: Dict[str, "asyncio.Task"],
    timeout: float = SOURCE_PHASE_TIMEOUT_SECS,
) -> Dict[str, Any]:
    """Await every upstream source under one overall deadline.

    Returns ``{name: value}`` for sources that answered and ``{name: None}``
    for sources that failed or overran. Unfinished tasks are cancelled and
    awaited so a stuck curl_cffi socket cannot outlive the fetch phase. A
    source that legitimately reports zero events keeps its value, so callers
    can still tell "no racing today" from "no answer".
    """
    if not pending:
        return {}
    done, not_done = await asyncio.wait(set(pending.values()), timeout=timeout)
    results: Dict[str, Any] = {}
    for name, task in pending.items():
        if task in done:
            if task.cancelled():
                results[name] = None
                continue
            exc = task.exception()
            results[name] = None if exc is not None else task.result()
        else:
            task.cancel()
            results[name] = None
    if not_done:
        await asyncio.gather(*not_done, return_exceptions=True)
    return results


def _sast_to_utc(off_time: Optional[datetime]) -> Optional[datetime]:
    """Convert a SAST wall-clock datetime to the container's UTC frame (-2h).

    Betfair stamps ``bf_off_time`` as a SAST wall clock; the monitor container
    runs UTC. SA has no DST, so a flat -2h shift is exact (mirrors the inverse
    of ``_sast_wall``).
    """
    if off_time is None:
        return None
    try:
        return off_time - timedelta(hours=2)
    except (TypeError, ValueError, OverflowError):
        return None


def _close_overdue_races(events: dict, max_minutes_after_off: int = 5) -> dict:
    """Remove races whose scheduled off-time has passed by > max_minutes_after_off.

    Time preference: ``bf_off_time`` (stamped by the Betfair merge, SAST wall)
    converted to UTC, then Betway display times (``t``/``st``). Catches races
    where Betway never sets isFinished (common for UK/Ireland tracks) and where
    Betway display times are placeholders. Races with no parseable time from
    any source are stamped ``first_seen`` and dropped once older than
    UNPARSEABLE_RACE_TTL_SECS so they cannot persist indefinitely.

    Betfair-only events (bf_off_time present but no Betway t/st) that are
    older than 2h are also dropped — these are ghost markets that Betfair
    keeps open for settlement but Betway never listed.

    Surviving races are stamped ``expires_at`` (epoch secs = off-time + grace)
    so readers that see a snapshot minutes later (HUD, worker KV, Telegram)
    can still drop a race that finished in the meantime.
    """
    now = datetime.now()
    grace_secs = max_minutes_after_off * 60
    filtered = {}
    for eid, e in events.items():
        bf_off = _sast_to_utc(_parse_race_off_time(e.get("bf_off_time")))
        bw_time = e.get("t") or e.get("st")
        off_time = bf_off or (_parse_race_off_time(bw_time) if bw_time else None)
        if off_time:
            if (now - off_time).total_seconds() > grace_secs:
                logger.info(f"Race auto-closed by off-time: {e.get('en','?')} R{e.get('raceNumber','?')} (off {e.get('bf_off_time') or bw_time}, now {now.strftime('%H:%M')})")
                continue
            e.pop("first_seen", None)
            e["expires_at"] = off_time.timestamp() + grace_secs
            filtered[eid] = e
            continue
        # No parseable time from any source: stamp first sight, TTL-drop old ones.
        first_seen = e.get("first_seen")
        try:
            age = now.timestamp() - float(first_seen) if first_seen is not None else None
        except (TypeError, ValueError):
            age = None
        if age is None:
            e["first_seen"] = now.timestamp()
            filtered[eid] = e
            continue
        if age > UNPARSEABLE_RACE_TTL_SECS:
            logger.info(f"Race dropped by first-seen TTL: {e.get('en','?')} R{e.get('raceNumber','?')} (unparseable off-time, seen {age / 3600:.1f}h)")
            continue
        filtered[eid] = e

    # Second pass: drop Betfair-only ghost events. These are races that
    # Betfair keeps open for settlement (often 2h+) but Betway never listed
    # (no Betway-native t/st field). Without this pass they re-inflate the
    # dashboard count on every cycle via the last-good fallback cache.
    _BF_ONLY_GHOST_SECS = 2 * 60 * 60  # 2 hours
    cleaned = {}
    for eid, e in filtered.items():
        if e.get("bf_off_time") and not (e.get("t") or e.get("st")):
            # Betfair-injected only — check age via bf_off_time
            bf_off2 = _sast_to_utc(_parse_race_off_time(e.get("bf_off_time")))
            if bf_off2 and (now - bf_off2).total_seconds() > _BF_ONLY_GHOST_SECS:
                logger.info(
                    "Betfair-only ghost dropped: %s R%s (bf_off_time %s, age %.1fh)",
                    e.get("en", "?"), e.get("raceNumber", "?"),
                    e.get("bf_off_time", "?"),
                    (now - bf_off2).total_seconds() / 3600,
                )
                continue
        cleaned[eid] = e
    return cleaned


def _recover_empty_snapshot(state: dict) -> dict:
    """Guard against persisting a 0-race card.

    A cycle can legitimately prune to zero at the end of the racing day, but a
    *sudden* empty result while the previous snapshot's races are still current
    is almost always an upstream hiccup (Betway returns HTTP 200 with an empty
    card, a parse miss, a partial feed). Persisting that blanks the HUD, the KV
    odds cache and Telegram at once — the "data keeps disappearing" symptom.

    Recovery: re-sanitize the previous file's events (so expired/finished races
    are still dropped) and reuse the survivors, stamped ``stale`` with a
    ``SNAPSHOT_EMPTY_GUARD`` healing event. When the previous card has genuinely
    expired, the sanitizer returns nothing and the empty state stands.
    """
    try:
        with open(MARKET_SNAPSHOT_PATH) as f:
            prev = json.load(f)
    except Exception as exc:
        logger.debug("Empty-snapshot guard: no previous file (%s)", exc)
        return state

    prev_events = prev.get("events") if isinstance(prev, dict) else None
    if not prev_events:
        return state

    try:
        from core_agent.core.snapshot_writer import sanitize_snapshot

        recovered = sanitize_snapshot({"events": prev_events}, source="monitor")["events"]
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Empty-snapshot guard: sanitize failed (%s)", exc)
        return state

    if not recovered:
        # Previous card is genuinely over — accept the empty result.
        return state

    guarded = dict(state)
    guarded["events"] = recovered
    guarded["stale"] = True
    guarded.setdefault("stale_since", datetime.now().isoformat())
    _write_healing_event(
        "SNAPSHOT_EMPTY_GUARD",
        f"Cycle pruned to 0 races while {len(recovered)} previous race(s) were still current — reusing them (stale)",
        status="WARN",
    )
    logger.warning(
        "Empty-snapshot guard: cycle produced 0 races, reusing %d still-current race(s)",
        len(recovered),
    )
    return guarded


def _race_num_from_text(text) -> int:
    """Best-effort race number from a race-name string ("R5 1800m Mdn" -> 5).

    Used by the Betfair merge fallback when the event carries no explicit
    ``raceNumber`` (stale caches, bet-type market names). Returns -1 when
    unparseable so callers can skip without raising.
    """
    if not isinstance(text, str):
        return -1
    import re as _re

    m = _re.search(r"\bR(\d{1,2})\b", text)
    if not m:
        return -1
    try:
        return int(m.group(1))
    except (ValueError, TypeError):
        return -1


def _norm_course(c: str) -> str:
    """Normalise course name for cross-source matching."""
    n = c.lower().strip()
    n = n.replace(" racecourse", "").replace(" park", "").strip()
    # Also normalise hyphens: "Lingfield Park" vs "lingfield-park"
    n = n.replace("-", " ").replace("_", " ").strip()
    return _normalise(n)


def _merge_ro_into(betway_state: dict, ro_snapshot: dict):
    """Inject racing-odds.com data into matching Betway events/runners.

    Matches by (date, course, time) with fuzzy fallbacks for
    date offsets (±1 day), course name variations, and horse name
    variations via difflib.
    """
    ro_events = ro_snapshot.get("events", {})
    if not ro_events:
        logger.info("Racing-Odds returned no events -- skipping merge")
        return

    # Build lookup keyed by (date, course)
    ro_lookup: Dict[str, Dict] = {}
    for e in ro_events.values():
        date = e.get("date", "")
        key = f"{date}|{_norm_course(e.get('course',''))}|{_norm_time(e.get('t',''))}"
        ro_lookup[key] = {
            "horses": {_normalise(r["name"]): r for r in e.get("runners", [])},
            "horse_names": [_normalise(r["name"]) for r in e.get("runners", [])],
            "original_horses": {_normalise(r["name"]): r["name"] for r in e.get("runners", [])},
        }

    today_str = datetime.now().strftime("%Y-%m-%d")
    # Also try yesterday / tomorrow for date-offset matching
    date_candidates = [today_str]
    try:
        dt = datetime.strptime(today_str, "%Y-%m-%d")
        date_candidates.append((dt - timedelta(days=1)).strftime("%Y-%m-%d"))
        date_candidates.append((dt + timedelta(days=1)).strftime("%Y-%m-%d"))
    except ValueError:
        pass

    merged_races = 0
    fuzzy_horse_matches = 0
    for event in betway_state.get("events", {}).values():
        bw_course = _norm_course(event.get("course", ""))
        bw_time = _norm_time(event.get("t", ""))
        ro_match = None

        # Try exact match across candidate dates
        for d in date_candidates:
            key = f"{d}|{bw_course}|{bw_time}"
            ro_match = ro_lookup.get(key)
            if ro_match:
                break

        # Fallback: try fuzzy course matching (strip more aggressively)
        if not ro_match:
            bw_course_stripped = bw_course.replace("park", "").replace("racecourse", "").replace(" ", "").strip()
            for d in date_candidates:
                for rok, rov in ro_lookup.items():
                    rok_course = _norm_course(rok.split("|")[1]) if "|" in rok else ""
                    rok_stripped = rok_course.replace("park", "").replace("racecourse", "").replace(" ", "").strip()
                    if rok_stripped == bw_course_stripped and rok.endswith(f"|{bw_time}"):
                        ro_match = rov
                        break
                if ro_match:
                    break

        if not ro_match:
            continue

        merged_races += 1
        for runner in event.get("runners", []):
            rn = _normalise(runner.get("name", ""))
            ro_horse = ro_match["horses"].get(rn)
            if not ro_horse:
                # Fuzzy horse name matching
                matches = difflib.get_close_matches(rn, ro_match["horse_names"], n=1, cutoff=0.6)
                if matches:
                    ro_horse = ro_match["horses"].get(matches[0])
                    fuzzy_horse_matches += 1
            if ro_horse:
                runner["ro_odds"] = ro_horse.get("odds")
                runner["ro_bookmakers"] = ro_horse.get("ro_bookmakers", {})

    logger.info(
        "Racing-Odds merged into %d/%d Betway races (fuzzy horse matches: %d)",
        merged_races, len(betway_state.get("events", {})), fuzzy_horse_matches,
    )


def _sast_wall(time_hhmm: str) -> str:
    """Shift a UTC wall-clock HH:MM to SAST wall-clock (+2h, no DST in SA).

    Betway display times are UTC walls (epoch rendered in UTC containers)
    while Betfair stamps SAST walls (epoch rendered with tz=_SAST) — the
    same instant reads 2h apart ("12:40" vs "14:40"). Comparing in one
    frame is what makes UK/IRE cards (whose race names carry no R-number
    for the raceNumber fallback) merge at all. Returns "" when unparseable.
    """
    try:
        parts = str(time_hhmm or "").strip().split(":")
        h, m = int(parts[0]), int(parts[1])
        return f"{(h + 2) % 24:02d}:{m:02d}"
    except (ValueError, TypeError, IndexError):
        return ""


def _merge_bf_into(betway_state: dict, bf_snapshot: dict) -> None:
    """Inject Betfair SA form data (gear + days since last run) into matching
    Betway events/runners. Adds two optional fields per runner; never modifies
    existing snapshot fields, never raises.

    Matching: scope per (course, time). Horse names: exact-first (whitespace/
    case-normalized) then ``difflib`` fuzzy (0.6 cutoff). One-to-one
    assignment: already-matched Betfair runners are excluded from later
    candidate pools so two SA horses with similar names can't swap gear.
    """
    bf_events = bf_snapshot.get("events") if isinstance(bf_snapshot, dict) else None
    if not bf_events:
        logger.info("Betfair SA returned no events -- skipping merge")
        return

    merged_races = 0
    fuzzy_horse_matches = 0
    for event in betway_state.get("events", {}).values():
        course_key = _norm_course(event.get("course", ""))
        time_key = _norm_time(event.get("t", ""))
        if not course_key or not time_key:
            continue

        bf_match = None
        time_sast = _sast_wall(time_key)
        # Two passes: exact-frame first, UTC->SAST shifted second. A single
        # pass could pair a race with a different race 2h later in meetings
        # where both frames appear.
        for shifted in (False, True):
            for bf in bf_events.values():
                if not isinstance(bf, dict):
                    continue
                if _norm_course(bf.get("course", "")) != course_key:
                    continue
                bf_time = _norm_time(bf.get("t", ""))
                # Exact match (same frame) or UTC->SAST shifted match: Betway
                # times are UTC walls, Betfair times SAST walls ("12:40" UTC
                # is "14:40" SAST — same instant, different wall clock).
                want = time_sast if shifted else time_key
                if not want or bf_time != want:
                    continue
                bf_match = bf
                break
            if bf_match:
                break
        if not bf_match:
            # Fallback: same course + same race number. Betway display times
            # can be placeholders ("12:00") while Betfair carries the exact
            # off-time, which would otherwise block the whole merge.
            try:
                bw_race_num = int(event.get("raceNumber", event.get("race_number", -1)))
            except (ValueError, TypeError):
                bw_race_num = -1
            if bw_race_num > 0:
                for bf in bf_events.values():
                    if not isinstance(bf, dict):
                        continue
                    if _norm_course(bf.get("course", "")) != course_key:
                        continue
                    try:
                        bf_race_num = int(bf.get("raceNumber", -1))
                    except (ValueError, TypeError):
                        bf_race_num = -1
                    if bf_race_num < 0:
                        # Stale caches predate the raceNumber field; the /all
                        # race name ("R5 1800m Mdn") still carries it.
                        bf_race_num = _race_num_from_text(bf.get("raceName"))
                    if bf_race_num == bw_race_num:
                        bf_match = bf
                        break
        if not bf_match:
            continue

        # Stamp the exact Betfair off-time (additive only). Downstream gates
        # prefer this over display times that may be placeholders.
        bf_off = bf_match.get("offTime")
        if bf_off and "bf_off_time" not in event:
            event["bf_off_time"] = bf_off
        bf_date = bf_match.get("eventDate")
        if bf_date and "bf_event_date" not in event:
            event["bf_event_date"] = bf_date
        bf_dist = bf_match.get("distanceM")
        if bf_dist and "distance_m" not in event:
            event["distance_m"] = bf_dist

        bf_runners = bf_match.get("runners") or []
        if not bf_runners:
            continue

        matched_bf_indices: set = set()
        for bw_runner in event.get("runners") or []:
            bw_name = (bw_runner.get("name") or bw_runner.get("outcomeName") or "").strip()
            if not bw_name:
                continue
            bw_norm = _bf_normalise(bw_name)

            # 1. Exact match (case + whitespace insensitive)
            chosen_idx = -1
            for i, r in enumerate(bf_runners):
                if i in matched_bf_indices:
                    continue
                bf_name = (r.get("name") or "").strip()
                if bf_name and _bf_normalise(bf_name) == bw_norm:
                    chosen_idx = i
                    break

            # 2. Fuzzy fallback (0.6 cutoff, one-to-one)
            if chosen_idx < 0:
                candidates = [
                    (i, _bf_normalise(r.get("name") or ""))
                    for i, r in enumerate(bf_runners)
                    if i not in matched_bf_indices and r.get("name")
                ]
                if not candidates:
                    continue
                matches = difflib.get_close_matches(
                    bw_norm,
                    [n for _, n in candidates],
                    n=1,
                    cutoff=0.6,
                )
                if matches:
                    target_norm = matches[0]
                    for i, n in candidates:
                        if n == target_norm:
                            chosen_idx = i
                            fuzzy_horse_matches += 1
                            break

            if chosen_idx < 0:
                continue
            matched_bf_indices.add(chosen_idx)
            bf_runner = bf_runners[chosen_idx]

            # 3. Attach (additive only; never overwrite existing fields)
            for key in (
                "gear",
                "daysSinceRun",
                "runner_comments",
                "jockey_claim",
                "official_rating",
                "pedigree",
                "owner",
                "verdict",
                "trainer",
                "age",
                "weight",
                "form",
            ):
                val = bf_runner.get(key)
                if val is not None and val != "" and key not in bw_runner:
                    bw_runner[key] = val
            # Non-runner flag travels both ways: Betfair REMOVED stamps the
            # Betway runner, and Betfair-only NRs (scratched after Betway
            # cached, or never listed) are injected so the NR signal can't
            # vanish — settlement auto-VOIDs on this, HUD badges it.
            if bf_runner.get("non_runner") and not bw_runner.get("non_runner"):
                bw_runner["non_runner"] = True
        # Inject unmatched Betfair non-runners (they can't win, but the
        # roster must show them as scratched, not silently absent).
        try:
            _existing = {
                _bf_normalise(str(rr.get("name") or rr.get("outcomeName") or ""))
                for rr in (event.get("runners") or []) if isinstance(rr, dict)
            }
            for _i, _br in enumerate(bf_runners):
                if _i in matched_bf_indices or not _br.get("non_runner"):
                    continue
                _bn = str(_br.get("name") or "").strip()
                if not _bn or _bf_normalise(_bn) in _existing:
                    continue
                (event.get("runners") or []).append({
                    "name": _bn,
                    "outcomeName": _bn,
                    "odds": "NR",
                    "non_runner": True,
                })
                _existing.add(_bf_normalise(_bn))
        except Exception:
            pass
        merged_races += 1

    logger.info(
        "Betfair SA merged into %d/%d Betway races (fuzzy horse matches: %d)",
        merged_races, len(betway_state.get("events", {})), fuzzy_horse_matches,
    )


def _merge_daily_scan_into(state: dict):
    """Merge today's daily scan value bets, favorites, and outsiders into active events."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_scan_file = os.path.join(str(DATA_DIR), f"daily_scan_{today_str}.json")

    scan_data = {}
    if os.path.exists(daily_scan_file):
        try:
            with open(daily_scan_file, "r") as f:
                scan_data = json.load(f)
        except Exception as e:
            logger.debug("Failed to read daily scan JSON: %s", e)

    # Normalize track keys in scan_data
    scan_lookup = {}
    if isinstance(scan_data, dict):
        for track_name, races in scan_data.items():
            if isinstance(races, list):
                scan_lookup[track_name.lower().replace(" ", "")] = races

    for event in state.get("events", {}).values():
        course_norm = _norm_course(event.get("course", ""))
        race_num = event.get("raceNumber")
        if race_num is None:
            continue
        try:
            race_num = int(race_num)
        except ValueError:
            continue

        # Extract runners from event
        runners_list = event.get("runners", [])
        if not runners_list:
            continue

        # 1. Determine Favourite from live market odds (lowest decimal odds > 1.0)
        fav_runner = None
        min_odds = 9999.0
        for r in runners_list:
            try:
                odds_val = float(r.get("odds", 9999.0))
                if 1.0 < odds_val < min_odds:
                    min_odds = odds_val
                    fav_runner = r
            except (ValueError, TypeError):
                pass
        if not fav_runner:
            fav_runner = runners_list[0]

        # 2. Determine Outsider from live market odds (highest decimal odds)
        max_live_odds = -1.0
        live_outsider_runner = None
        for r in runners_list:
            try:
                odds_val = float(r.get("odds", 0.0))
                if odds_val > max_live_odds:
                    max_live_odds = odds_val
                    live_outsider_runner = r
            except (ValueError, TypeError):
                pass
        if not live_outsider_runner:
            live_outsider_runner = runners_list[-1]

        # Look up track and race in scan data
        scanned_race = None
        races_list = scan_lookup.get(course_norm.replace(" ", ""))
        if races_list:
            scanned_race = next((r for r in races_list if r.get("race_number") == race_num), None)

        val_runner = None
        outsider_runner = None

        if scanned_race:
            value_bets = scanned_race.get("value_bets", [])
            max_edge = 0.0
            max_outsider_odds = 0.0

            for vb in value_bets:
                vb_horse = _normalise(vb.get("horse", ""))
                edge = float(vb.get("edge_percent", 0.0) or vb.get("edge", 0.0))
                odds_dec = float(vb.get("odds_decimal", 0.0) or vb.get("odds", 0.0) or 2.0)

                # Match with runner in event
                matched_r = None
                for r in runners_list:
                    if _normalise(r.get("name", "")) == vb_horse:
                        matched_r = r
                        break
                
                if not matched_r:
                    # Fuzzy fallback
                    import difflib
                    names = [r.get("name", "") for r in runners_list]
                    norm_names = [_normalise(n) for n in names]
                    matches = difflib.get_close_matches(vb_horse, norm_names, n=1, cutoff=0.7)
                    if matches:
                        matched_idx = norm_names.index(matches[0])
                        matched_r = runners_list[matched_idx]

                if matched_r:
                    # Set runner's edge and probability
                    matched_r["edge"] = edge
                    matched_r["winProbability"] = float(vb.get("estimated_probability", 0.0))

                    # Track highest edge for the "Value Bet" option
                    if edge > max_edge:
                        max_edge = edge
                        val_runner = matched_r

                    # Track "Shout-Outsider" (value bet with odds >= 8.0)
                    if odds_dec >= 8.0 and odds_dec > max_outsider_odds:
                        max_outsider_odds = odds_dec
                        outsider_runner = matched_r

        # Populate payload with strict fallbacks
        event["aiSelections"] = {
            "value": val_runner or runners_list[0],
            "favourite": fav_runner or runners_list[0],
            "outsider": outsider_runner or live_outsider_runner or runners_list[-1]
        }


# ATR content changes slowly (movers a few times/day, results 1-2x/day) but the
# 5-min cron was hitting 4 ATR pages every cycle (~1150 fetches/day from Modal
# egress IPs). On 2026-09-03 that volume got us rate-limited into Fastly
# challenge shells for 18h straight. Refresh ATR at most every 45 min.
ATR_REFRESH_MIN_GAP_SECS = 45 * 60


def _atr_file_fresh(path, max_age_secs: int = ATR_REFRESH_MIN_GAP_SECS) -> bool:
    """True when a single ATR snapshot file was written within max_age_secs.

    Used for per-file gating: when only one feed (e.g. movers) is stale, retry
    just that feed instead of re-hammering all four ATR pages every cycle.
    """
    import time as _time
    try:
        p = Path(path)
        return p.exists() and (_time.time() - p.stat().st_mtime) < max_age_secs
    except Exception:
        return False


def _atr_predictor_fresh(max_age_secs: int = ATR_REFRESH_MIN_GAP_SECS) -> bool:
    """True when the predictor's last SUCCESS is within max_age_secs.

    A failed predictor attempt still rewrites the snapshot — that is how the HUD
    learns the reason — but keeps the previous `timestamp`. Judging the gate by
    file mtime therefore read "fresh" after every failure and the feed was never
    retried (Nov-2026: 18.8h stale with the file rewritten every cycle). The
    payload's own timestamp is the only honest signal; mtime is the fallback for
    legacy snapshots that have none.
    """
    from datetime import datetime as _dt

    p = Path(ATR_PREDICTOR_PATH)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text())
    except Exception:
        return False
    ts = data.get("timestamp") if isinstance(data, dict) else None
    if not ts:
        return _atr_file_fresh(p, max_age_secs)
    try:
        when = _dt.fromisoformat(str(ts).replace("Z", "+00:00"))
        now = _dt.now(when.tzinfo) if when.tzinfo else _dt.now()
        return (now - when).total_seconds() < max_age_secs
    except Exception:
        return _atr_file_fresh(p, max_age_secs)


def _atr_snapshot_fresh(max_age_secs: int = ATR_REFRESH_MIN_GAP_SECS) -> bool:
    """True when ALL three ATR snapshots hold data younger than max_age_secs.

    Predictor freshness comes from its last-success timestamp rather than mtime
    (see _atr_predictor_fresh) — otherwise a rewritten failure record would make
    the whole set look current and short-circuit the retry.
    """
    try:
        if not _atr_file_fresh(ATR_RESULTS_PATH, max_age_secs):
            return False
        if not _atr_file_fresh(ATR_MOVERS_PATH, max_age_secs):
            return False
        return _atr_predictor_fresh(max_age_secs)
    except Exception:
        return False


def _atr_result_key(race: Dict[str, Any]) -> tuple:
    """Identity of one race inside a snapshot: (day, course, race number).

    Days must be absolute. Relative labels ("yesterday") made merged entries
    re-date themselves against the newest snapshot timestamp, so a card two
    days old silently settled as yesterday's.
    """
    title = str(race.get("title") or "")
    m = re.match(r"\s*(\d+)", title)
    race_no = m.group(1) if m else str(race.get("time") or "")
    return (
        str(race.get("date") or "")[:10],
        str(race.get("course") or "").strip().lower(),
        race_no,
    )


def _atr_absolutize(results: List[Dict], snap_ts: Optional[str]) -> List[Dict]:
    """Rewrite relative day labels ("yesterday") as absolute ISO dates.

    Legacy snapshots stored the request label. Merged into a newer snapshot
    those entries re-dated themselves against the new timestamp, so a card two
    days old could settle as yesterday's. Resolve them against the timestamp of
    the snapshot they were captured in, once, then never again.
    """
    from datetime import datetime as _dt

    snap_day = None
    if snap_ts:
        try:
            snap_day = _dt.fromisoformat(str(snap_ts).replace("Z", "+00:00")).date()
        except Exception:
            snap_day = None

    out = []
    for race in results or []:
        if not isinstance(race, dict):
            continue
        day = str(race.get("date") or "").strip().lower()
        if not re.match(r"^\d{4}-\d{2}-\d{2}", day) and snap_day:
            if day in ("today", ""):
                race = {**race, "date": snap_day.isoformat()}
            elif day in ("yesterday", "yday"):
                race = {**race, "date": (snap_day - timedelta(days=1)).isoformat()}
        out.append(race)
    return out


def _atr_snapshot_days(path) -> set:
    """ISO days already captured in a results snapshot."""
    try:
        blob = json.loads(Path(path).read_text())
    except Exception:
        return set()
    results = _atr_absolutize(blob.get("results") or [], blob.get("timestamp"))
    days = set()
    for race in results:
        day = str(race.get("date") or "")[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            days.add(day)
    return days


def _atr_yesterday_iso(now: Optional[datetime] = None) -> str:
    return ((now or datetime.now()) - timedelta(days=1)).date().isoformat()


# A racing day is not finished when the date rolls over. Meeting dates are
# labels, not clocks: a US card labelled "8 Nov" still runs into 04:00 SAST on
# the 9th. The old rule skipped "yesterday" the moment the day appeared in the
# snapshot at all, so every evening card froze at whatever had finished by the
# rollover (Nov-2026: 2026-11-08 stuck at Gulfstream R1-R3 + Churchill R1 and
# 13 picks could never settle). Keep refetching a day while it is still growing
# and stop once nothing new has landed for this long.
ATR_CARD_QUIET_SECS = 6 * 3600


def _atr_day_signature(races: List[Dict]) -> str:
    """Fingerprint of one day's card: meetings, race numbers, result depth."""
    import hashlib as _hashlib

    rows = []
    for race in races or []:
        if not isinstance(race, dict):
            continue
        runners = race.get("runners") or []
        placed = sum(
            1 for r in runners
            if isinstance(r, dict) and str(r.get("position") or "").strip()
        )
        rows.append(
            f"{str(race.get('course') or '').strip().lower()}|"
            f"{_atr_result_key(race)[2]}|{len(runners)}|{placed}"
        )
    return _hashlib.sha1("\n".join(sorted(rows)).encode()).hexdigest()


def _atr_captured(path) -> Dict[str, Dict[str, Any]]:
    """Per-day capture bookkeeping from a results snapshot.

    Legacy snapshots have no ``captured`` map; their file mtime is the honest
    "last time anything landed" for every day they hold.
    """
    try:
        blob = json.loads(Path(path).read_text())
    except Exception:
        return {}
    cap = blob.get("captured") if isinstance(blob, dict) else None
    if isinstance(cap, dict) and cap:
        return {str(k)[:10]: v for k, v in cap.items() if isinstance(v, dict)}

    results = _atr_absolutize(blob.get("results") or [], blob.get("timestamp"))
    try:
        mtime = Path(path).stat().st_mtime
    except Exception:
        mtime = 0.0
    # A legacy snapshot cannot have grown after it was written, so its own
    # timestamp is a tighter bound than mtime (which is "now" right after a
    # deploy and would keep every old day alive for the full quiet window).
    last = mtime
    try:
        last = datetime.fromisoformat(
            str(blob.get("timestamp") or "").replace("Z", "+00:00")
        ).timestamp()
    except Exception:
        pass
    out: Dict[str, Dict[str, Any]] = {}
    for race in results:
        day = str(race.get("date") or "")[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            continue
        out.setdefault(day, {"races": 0, "last_grew_at": last})["races"] += 1
    return out


def _atr_update_capture(
    previous: Dict[str, Dict[str, Any]],
    merged: List[Dict],
    now_ts: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """Refresh the per-day capture map after a merge.

    ``last_grew_at`` only moves when the day's card actually changed — a plain
    re-fetch of an unchanged page must not keep a finished day alive forever.
    """
    import time as _time

    now_ts = _time.time() if now_ts is None else now_ts
    by_day: Dict[str, List[Dict]] = {}
    for race in merged or []:
        if not isinstance(race, dict):
            continue
        day = str(race.get("date") or "")[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            by_day.setdefault(day, []).append(race)

    out: Dict[str, Dict[str, Any]] = {}
    for day, races in by_day.items():
        sig = _atr_day_signature(races)
        prev = previous.get(day) or {}
        grew_at = prev.get("last_grew_at")
        if prev.get("signature") != sig or not grew_at:
            grew_at = now_ts
        out[day] = {
            "races": len(races),
            "courses": sorted({str(r.get("course") or "").strip() for r in races if r.get("course")}),
            "signature": sig,
            "first_seen_at": prev.get("first_seen_at") or now_ts,
            "last_grew_at": grew_at,
        }
    return out


def _atr_day_needs_finishing(
    path, day: str, now_ts: Optional[float] = None
) -> bool:
    """True while a day's card can still produce new results.

    Never captured -> fetch. Captured but still growing (or grown within the
    last ATR_CARD_QUIET_SECS) -> keep fetching, because late meetings on the
    card are still running. Quiet for the whole window -> finished.
    """
    import time as _time

    now_ts = _time.time() if now_ts is None else now_ts
    cap = _atr_captured(path).get(str(day)[:10])
    if not cap or not cap.get("races"):
        return True
    try:
        last = float(cap.get("last_grew_at"))
    except (TypeError, ValueError):
        return True
    if last > now_ts:  # clock skew — treat as "just grew"
        return True
    return (now_ts - last) < ATR_CARD_QUIET_SECS


def _atr_merge_results(existing: List[Dict], fresh: List[Dict], keep_days: int = 3) -> List[Dict]:
    """Merge fresh races over the existing snapshot, newest wins, pruned by age.

    Pruning keeps the file from growing forever (the page duplicates races and
    the merge used to append them indefinitely).
    """
    merged: Dict[tuple, Dict[str, Any]] = {}
    for race in list(existing or []) + list(fresh or []):
        if not isinstance(race, dict):
            continue
        key = _atr_result_key(race)
        prev = merged.get(key)
        # An enriched full card (whole finishing order) must survive a later
        # thin /results summary for the same race — full is a superset of
        # summary for a race that ran, so more runners always wins.
        if prev is None or len(race.get("runners") or []) >= len(prev.get("runners") or []):
            merged[key] = race

    if not keep_days:
        return list(merged.values())

    cutoff = (datetime.now() - timedelta(days=keep_days)).date().isoformat()
    kept = []
    for key, race in merged.items():
        day = key[0]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day) or day >= cutoff:
            kept.append(race)
    return kept


def _atomic_write_json(path: str, data: any, indent: int = 2):
    """Write data to a JSON file atomically to prevent corruption on crash"""
    tmp_path = str(path) + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=indent, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"[WARN] Failed atomic write to {path}: {e}")


def _write_healing_event(action: str, details: str, agent: str = "OddsMonitor", status: str = "SUCCESS"):
    """Append a healing event to the shared log file atomically."""
    try:
        events = []
        if os.path.exists(HEALING_EVENTS_PATH):
            with open(HEALING_EVENTS_PATH) as f:
                events = json.load(f)
        events.append({
            "id": f"{action.lower()}-{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "agent": agent,
            "status": status,
        })
        _atomic_write_json(HEALING_EVENTS_PATH, events[-50:])  # keep last 50
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("L7-Monitor")


class AdaptiveOddsMonitor:
    def __init__(self):
        self.intel_cache = IntelligenceCacheManager(
            MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR
        )
        self._telegram_notifier: Optional[TelegramNotifier] = None
        try:
            from core_agent.skills.notifications.telegram_bot import TelegramNotifier
            self._telegram_notifier = TelegramNotifier()
        except Exception:
            pass

        self._digester: Optional[AlertDigester] = None
        if self._telegram_notifier:
            self._digester = AlertDigester(self._telegram_notifier)
            self._digester.start()

        self.alert_engine = AlertEngine(
            notification_callback=self._on_alert
        )
        self.betway = BetwayAPI()
        self.racing_odds = RacingOddsAPI()
        self.betfair = BetfairSA()
        self.at_races = AtTheRacesAPI()
        # Last-good cache path for Betfair form data (used when a cycle fails
        # so the snapshot still carries gear/days from the most recent good fetch).
        self._bf_last_good_path = os.path.join(str(DATA_DIR), "betfair_form_last_good.json")

        self.monitoring_active = True
        # Per race+horse alert gate (Sep-2026: the old single *_last_alert_ts*
        # made the first trigger of a sweep suppress every other runner in
        # all ~40 races, so each digest carried ONE horse). ``_last_alert_ts``
        # stays for introspection only — the dict below is the live gate.
        self._last_alert_ts: float = 0
        self._last_alert_by_key: dict = {}
        self._alert_cooldown: float = 120.0

    async def _fetch_betfair_form_safely(self) -> dict:
        """Fetch Betfair SA form data through the rolling per-race cache.

        The live feed itself drops every market at its off-time, so a failed
        or empty cycle used to blank Betfair fields off the whole card while
        a long-lived file cache re-injected finished races ("Betfair data
        blinks / old races come back", Sep-2026).

        Cache discipline (mirrors Betway's snapshot cache):

        1. Success → upsert every fetched market into the rolling cache.
        2. Failure/empty → replay the cache, but prune per race: markets whose
           off-time passed (beyond grace) and entries not refreshed for
           ``BF_ENTRY_TTL_SECS`` are dropped, so a stale cache can never
           resurrect a finished race.
        3. Never raises — an empty snapshot makes the merge a no-op.
        """
        empty = {"events": {}, "count": 0}
        try:
            form = await self.betfair.get_form_format()
        except Exception as e:
            _write_healing_event(
                "BETFAIR_FETCH_FAIL",
                f"Betfair SA fetch raised: {e!r}",
                agent="OddsMonitor",
                status="WARN",
            )
            return self._bf_cache_replay() or empty

        if not form or not form.get("events"):
            _write_healing_event(
                "BETFAIR_EMPTY",
                "Betfair SA returned no events this cycle",
                agent="OddsMonitor",
                status="WARN",
            )
            return self._bf_cache_replay() or empty

        # Upsert the fresh markets into the rolling cache (per-race TTL).
        cache = self._load_bf_cache()
        now_ts = datetime.now().timestamp()
        fresh = {
            mid: {**ev, "_bf_cached_at": now_ts}
            for mid, ev in (form.get("events") or {}).items()
            if isinstance(ev, dict)
        }
        cache.update(fresh)
        cache = self._prune_bf_events(cache)
        self._save_bf_cache(cache)
        return {"events": fresh, "count": len(fresh), "cached_count": len(cache)}

    def _bf_cache_path(self) -> str:
        return os.path.join(str(DATA_DIR), "betfair_form_last_good.json")

    def _load_bf_cache(self) -> dict:
        """Raw read of the rolling Betfair cache (tolerant; {} on any error)."""
        try:
            if not os.path.exists(self._bf_cache_path()):
                return {}
            with open(self._bf_cache_path()) as f:
                cached = json.load(f)
            events = cached.get("events") if isinstance(cached, dict) else None
            if not isinstance(events, dict):
                return {}
            # Back-compat: pre-rolling files have no per-entry stamp — fall
            # back to the file-level saved_at so their entries still age out.
            saved_at = cached.get("saved_at")
            if saved_at:
                try:
                    stamp = datetime.fromisoformat(saved_at).timestamp()
                    for ev in events.values():
                        if isinstance(ev, dict) and "_bf_cached_at" not in ev:
                            ev["_bf_cached_at"] = stamp
                except (TypeError, ValueError):
                    pass
            return events
        except Exception as e:
            logger.debug("Betfair SA cache read failed: %s", e)
            return {}

    def _save_bf_cache(self, events: dict) -> None:
        try:
            _atomic_write_json(
                self._bf_cache_path(),
                {"saved_at": datetime.now().isoformat(), "events": events},
            )
        except Exception as e:
            logger.debug("Betfair SA cache write failed: %s", e)

    @staticmethod
    def _bf_event_off_utc(ev: dict) -> Optional[datetime]:
        """UTC off-time for a Betfair event (epoch first, then SAST wall HH:MM)."""
        try:
            from core_agent.skills.parsers.betfair_sa import _betfair_off_utc

            return _betfair_off_utc(ev)
        except Exception:
            return _sast_to_utc(_parse_race_off_time(ev.get("offTime") or ev.get("t")))

    def _prune_bf_events(self, events: dict, now: Optional[datetime] = None) -> dict:
        """Drop finished Betfair markets and entries that stopped refreshing.

        Per-race — the point of the rolling cache: a market stays usable while
        its race is upcoming and disappears the moment it has run, no matter
        how old the surrounding file is.
        """
        now = now or datetime.now()
        now_ts = now.timestamp()
        kept: Dict[str, Any] = {}
        for mid, ev in events.items():
            if not isinstance(ev, dict):
                continue
            off = self._bf_event_off_utc(ev)
            if off is not None and (now - off).total_seconds() > BF_GHOST_GRACE_SECS:
                continue
            stamp = ev.get("_bf_cached_at")
            try:
                if stamp is not None and now_ts - float(stamp) > BF_ENTRY_TTL_SECS:
                    continue
            except (TypeError, ValueError):
                pass
            kept[mid] = ev
        return kept

    def _bf_cache_replay(self) -> Optional[dict]:
        """Cache replay for a failed cycle: pruned per race, never ghosted."""
        base = self._load_bf_cache()
        if not base:
            return None
        before = len(base)
        pruned = self._prune_bf_events(base)
        if not pruned:
            _write_healing_event(
                "BETFAIR_CACHE_STALE",
                f"Betfair SA cache had {before} entr(ies), all finished/expired — merge skipped",
                agent="OddsMonitor",
                status="WARN",
            )
            return None
        if len(pruned) != before:
            self._save_bf_cache(pruned)
        logger.info(
            "Betfair SA: replaying %d cached market(s) (%d pruned as finished/expired)",
            len(pruned), before - len(pruned),
        )
        return {"events": pruned, "count": len(pruned), "cached": True}

    async def _on_alert(self, msg: dict):
        """Callback fired by AlertEngine when a condition triggers."""
        if not self._telegram_notifier or not self._digester:
            return
        horse = msg.get("horse", "?")
        course = msg.get("course", "?")
        key = f"{course}::{horse}"
        now = datetime.now().timestamp()
        last = self._last_alert_by_key.get(key, 0.0)
        if now - last < self._alert_cooldown:
            logger.info(f"Alert rate-limited: {msg.get('type')} {horse} @ {course}")
            return
        # Bound the gate dict so a long day can't grow it without limit.
        if len(self._last_alert_by_key) >= 2000:
            newest = sorted(self._last_alert_by_key.items(), key=lambda kv: kv[1])[-1000:]
            self._last_alert_by_key = dict(newest)
        self._last_alert_by_key[key] = now
        tag = msg.get("type", "alert")
        odds = msg.get("odds", "?")
        html = (
            f"🐎 {horse} @ {course}\n"
            f"💰 Odds: {odds}"
        )
        # Alert Digest v2: structured meta rides alongside the legacy HTML
        # so the renderer can build journey rows; HTML stays the fallback.
        meta = {k: msg.get(k) for k in (
            "course", "horse", "odds", "race", "off", "mins_to_off",
            "journey", "enrich", "timestamp",
        ) if msg.get(k) is not None}
        if tag in ("odds_drop", "value_bet"):
            await self._digester.push(tag, html, meta=meta or None)
        else:
            await self._digester.push_critical(tag, html)

    async def initialize(self):
        await self.alert_engine.initialize()
        self.events_cache = self.intel_cache.rehydrate()

    def _volume_reload(self) -> None:
        """Refresh the mount so ATR mtimes are the last *committed* ones.

        Cron containers mount the volume at the last committed revision. With
        no reload, the previous cycle's write is invisible and the 45-min gate
        reads a stale mtime, so every 5-min cycle re-fetched ATR. On
        2026-11-06 that fetched results three times inside 10 minutes, burned
        the hourly browser allowance and tripped the 6h breaker (ATR frozen
        from 16:25 SAST onward).
        """
        try:
            from core_agent.core.volume_sync import sync_volume

            sync_volume(0)
        except Exception as exc:
            logger.debug("ATR volume reload skipped: %s", exc)

    def _volume_commit(self) -> None:
        """Persist fresh ATR snapshots for sibling containers and the gate."""
        try:
            import os

            if not os.getenv("MODAL_TASK_ID"):
                return
            import modal

            modal.Volume.from_name("strike-tips-data").commit()
        except Exception as exc:
            logger.debug("ATR volume commit skipped: %s", exc)

    async def _refresh_atr_feeds(self, state: dict) -> None:
        """Refresh the three ATR snapshots at most every 45 min, per feed.

        ATR content moves slowly; hammering all four pages every 5-min cycle
        got our egress IPs challenge-walled for 18h on 2026-09-03. A stale
        feed retries alone without re-hammering the fresh ones.
        """
        # The gate is only trustworthy when the mount is current.
        self._volume_reload()
        if _atr_snapshot_fresh():
            logger.debug("ATR snapshots fresh (<45min) — skipping ATR fetch this cycle")
            return

        wrote = False
        # One hourly browser allowance funds every stale page this cycle.
        # Without this the first stale feed (results) took the whole hour and
        # movers/predictor starved for days.
        try:
            stale_pages = 0
            if not _atr_file_fresh(ATR_RESULTS_PATH):
                stale_pages += 1
            if not _atr_file_fresh(ATR_MOVERS_PATH):
                stale_pages += 1
            if not _atr_predictor_fresh():
                stale_pages += 1
            if stale_pages:
                self.at_races.open_stealth_burst(stale_pages)
        except Exception as exc:
            logger.debug("ATR stealth burst open skipped: %s", exc)

        if _atr_file_fresh(ATR_RESULTS_PATH):
            logger.debug("ATR results fresh — skipping results fetch")
        else:
            results: List[Dict] = []
            # Order is load-bearing. Only the browser tier clears Fastly and it
            # is allowed once per hour, so whichever page is fetched first gets
            # the whole allowance. "today" is the page that changes during the
            # card — fetching "yesterday" first is why the snapshot only ever
            # held yesterday's races and evening results never appeared.
            days = ["today"]
            # A day simply *present* is not a day *captured*. Evening meetings
            # (US cards labelled 8 Nov run to 04:00 SAST on the 9th) keep
            # finishing after ATR's "today" has rolled over, so "yesterday" is
            # refetched until the card stops growing for ATR_CARD_QUIET_SECS.
            if _atr_day_needs_finishing(ATR_RESULTS_PATH, _atr_yesterday_iso()):
                days.append("yesterday")
            for day in days:
                try:
                    results.extend(await self.at_races.get_results(day) or [])
                except Exception as exc:
                    logger.debug("ATR %s results fetch skipped: %s", day, exc)
            if results:
                existing_results: List[Dict] = []
                old_ts = None
                try:
                    if Path(ATR_RESULTS_PATH).exists():
                        blob = json.loads(Path(ATR_RESULTS_PATH).read_text())
                        existing_results = blob.get("results") or []
                        old_ts = blob.get("timestamp")
                except Exception:
                    existing_results = []
                # Legacy snapshots carry "yesterday" labels; date them against
                # the snapshot they came from before merging into this one.
                existing_results = _atr_absolutize(existing_results, old_ts)
                merged = _atr_merge_results(existing_results, results)
                captured = _atr_update_capture(
                    _atr_captured(ATR_RESULTS_PATH), merged
                )
                _atomic_write_json(ATR_RESULTS_PATH, {
                    "results": merged,
                    "captured": captured,
                    "timestamp": datetime.now().isoformat(),
                })
                wrote = True

        if _atr_file_fresh(ATR_MOVERS_PATH):
            logger.debug("ATR movers fresh — skipping movers fetch")
        else:
            try:
                movers = await self.at_races.get_market_movers()
                if movers:
                    try:
                        from core_agent.skills.parsers.atr_enrich import attach_snapshot_context

                        movers = attach_snapshot_context(movers, state.get("events", {}))
                    except Exception:
                        pass
                    _atomic_write_json(ATR_MOVERS_PATH, {
                        "movers": movers,
                        "timestamp": datetime.now().isoformat(),
                    })
                    wrote = True
            except Exception as exc:
                logger.debug("ATR movers fetch skipped: %s", exc)

        if _atr_predictor_fresh():
            logger.debug("ATR predictor fresh — skipping predictor fetch")
        else:
            # Predictor is the one ATR feed that historically failed silently:
            # get_predictor() returns [] on timeout / empty scrape / throttle
            # and the snapshot kept its stale `timestamp` forever. Record the
            # attempt (and any failure reason) without clobbering the last good
            # prediction set, so the HUD and /racing/predictor/status can show
            # "stale + why" instead of an eternal "analysing...".
            reason = None
            predictions = None
            try:
                predictions = await self.at_races.get_predictor()
            except Exception as exc:
                reason = f"exception: {exc}"
                logger.warning("ATR predictor fetch raised: %s", exc)

            if getattr(self.at_races, "_self_throttled", False):
                throttled = True
                reason = reason or "browser tier throttled (retry after cooldown)"
            else:
                throttled = False

            # Read existing snapshot to preserve last-good predictions.
            existing: dict = {}
            try:
                if Path(ATR_PREDICTOR_PATH).exists():
                    existing = json.loads(Path(ATR_PREDICTOR_PATH).read_text())
            except Exception:
                existing = {}

            now_iso = datetime.now().isoformat()
            if predictions:
                try:
                    from core_agent.skills.parsers.atr_enrich import attach_snapshot_context

                    predictions = attach_snapshot_context(predictions, state.get("events", {}))
                except Exception:
                    pass
                payload = {
                    "predictions": predictions,
                    "timestamp": now_iso,          # last SUCCESS
                    "last_attempt": now_iso,
                    "last_error": None,
                }
                _atomic_write_json(ATR_PREDICTOR_PATH, payload)
                wrote = True
                logger.info("ATR predictor refreshed: %d predictions", len(predictions))
            else:
                if reason is None:
                    reason = "empty scrape (0 predictions parsed)"
                payload = {
                    "predictions": existing.get("predictions", []),
                    "timestamp": existing.get("timestamp"),   # last success unchanged
                    "last_attempt": now_iso,
                    "last_error": reason,
                }
                _atomic_write_json(ATR_PREDICTOR_PATH, payload)
                wrote = True
                logger.warning("ATR predictor fetch produced no data: %s", reason)

        if wrote:
            self._volume_commit()

    async def run_single_cycle(self):
        """Execute ONE odds sync cycle — for Modal scheduled cron (no infinite loop)."""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            # Stall detection: if the previous snapshot is older than
            # MONITOR_STALL_SECS the cron has been missing cycles — record it
            # in the healing log (internal only, no Telegram).
            try:
                with open(MARKET_SNAPSHOT_PATH) as f:
                    _prev = json.load(f)
                _prev_ts = _prev.get("timestamp") if isinstance(_prev, dict) else None
                if _prev_ts:
                    _gap = (datetime.now() - datetime.fromisoformat(_prev_ts)).total_seconds()
                    if _gap > MONITOR_STALL_SECS:
                        _write_healing_event(
                            "MONITOR_STALL",
                            f"Previous snapshot was {_gap / 60:.0f} min old at cycle start",
                            status="WARN",
                        )
            except Exception:
                pass
            bw_task = asyncio.create_task(self.betway.get_snapshot_format())
            ro_task = asyncio.create_task(self.racing_odds.get_snapshot_format(target_date=today_str))
            bf_task = asyncio.create_task(self._fetch_betfair_form_safely())
            sources = await _collect_sources(
                {"betway": bw_task, "racing_odds": ro_task, "betfair": bf_task},
                timeout=SOURCE_PHASE_TIMEOUT_SECS,
            )
            betway_state = sources["betway"]
            state = betway_state if isinstance(betway_state, dict) else {"events": {}, "count": 0}
            ro_snapshot = sources["racing_odds"] or {"events": {}, "count": 0}
            bf_snapshot = sources["betfair"] or {"events": {}, "count": 0}
            _merge_ro_into(state, ro_snapshot)
            _merge_bf_into(state, bf_snapshot)
            active = {
                eid: {**e, "en": " ".join(e.get("en", "").split())}
                for eid, e in state.get("events", {}).items()
                if not e.get("isFinished")
            }
            state["events"] = _close_overdue_races(active)
            if not state["events"]:
                state = _recover_empty_snapshot(state)
            state["count"] = len(state["events"])
            # Provenance for the cron's meeting gate: "no events" from a failed
            # fetch must never be cached as a dark day (2026-11-04: Betway 403
            # emptied the card, the gate read it as a dark day and stood down).
            state["fetch_ok"] = bool(
                isinstance(betway_state, dict) and betway_state.get("fetch_ok", True)
            )
            state["timestamp"] = datetime.now().isoformat()
            active_ids = list(state["events"].keys())
            _merge_daily_scan_into(state)
            _atomic_write_json(MARKET_SNAPSHOT_PATH, state)
            try:
                enrich_snapshot_with_insights(state)
            except Exception as e:
                logger.debug(f"Swarm enrichment skipped: {e}")
            try:
                from core_agent.core.snapshot_cache import set_snapshot, publish_snapshot
                from core_agent.core.task_queue import get_redis
                set_snapshot(state)
                redis_client = await get_redis()
                await publish_snapshot(redis_client, state)
            except Exception:
                pass
            try:
                from core_agent.core.cf_push import push_snapshot
                await push_snapshot(state)
            except Exception as exc:
                logger.debug("Cloudflare push skipped: %s", exc)
            await self._refresh_atr_feeds(state)
            await self._check_atr_staleness()
            await self._cleanup_atr_snapshots()
            for event_id in active_ids:
                self.intel_cache.update_baseline(event_id, state["events"][event_id].get("runners", []))
            self.intel_cache.prune_stale_data(active_ids)
            logger.info(f"👻 Single cycle synced {state.get('count')} races.")
            for event in state.get("events", {}).values():
                await self.alert_engine.evaluate_odds_update(event, cache=self.intel_cache)
            # Alert digests: cron containers die at cycle end — ship due
            # entries now or they die with the queue (Sep-2026: odds-drop
            # digests never left the monitor cron).
            if self._digester:
                try:
                    # Surface what the cooldowns suppressed, so a thin digest
                    # is explainable instead of looking like lost alerts.
                    try:
                        self._digester.note_suppressed(self.alert_engine.stats)
                    except Exception:
                        pass
                    await self._digester.flush_due()
                except Exception as exc:
                    logger.debug("Digest flush skipped: %s", exc)
            return state
        except Exception as e:
            logger.warning(f"⚠️ Single cycle error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    async def run(self):
        await self.initialize()
        if self._digester:
            await self._digester.start_async()

        # Start heartbeat loop — generates dreams + saves to ChromaDB every 5min
        from core_agent.core.heartbeat import run_heartbeat_loop
        from core_agent.skills.memory.chroma_memory import RacingMemory
        _memory = RacingMemory()
        asyncio.create_task(run_heartbeat_loop(_memory))

        # Start swarm researcher — fills missing form insights across all regions + polls news
        if _HAS_SWARM:
            asyncio.create_task(run_swarm_loop(interval=600))

        logger.info("🚀 L7 Monitor Active (Refactored: Pure Python Mode)")
        self._atr_cycle = 0

        active_count = 0

        while self.monitoring_active:
            self._atr_cycle += 1
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                # 1. Fetch Betway + Racing-Odds in parallel
                bw_task = asyncio.create_task(self.betway.get_snapshot_format())
                ro_task = asyncio.create_task(self.racing_odds.get_snapshot_format(target_date=today_str))
                bf_task = asyncio.create_task(self._fetch_betfair_form_safely())
                sources = await _collect_sources(
                    {"betway": bw_task, "racing_odds": ro_task, "betfair": bf_task},
                    timeout=SOURCE_PHASE_TIMEOUT_SECS,
                )
                betway_state = sources["betway"]
                state = betway_state if isinstance(betway_state, dict) else {"events": {}, "count": 0}
                ro_snapshot = sources["racing_odds"]
                if ro_snapshot is None:
                    ro_snapshot = {"events": {}, "count": 0}
                    logger.debug("Racing-Odds snapshot failed, skipping merge")
                bf_snapshot = sources["betfair"]
                if bf_snapshot is None:
                    bf_snapshot = {"events": {}, "count": 0}
                    logger.debug("Betfair SA form fetch failed, skipping merge")

                # 1b. Merge Racing-Odds data into Betway events where race/horse match
                _merge_ro_into(state, ro_snapshot)

                # 1c. Merge Betfair SA form (gear + days since last run) -- additive only
                _merge_bf_into(state, bf_snapshot)

                # 2. Persistence & Pruning
                # Remove Betway-finished races and normalize names
                active = {
                    eid: {**e, "en": " ".join(e.get("en", "").split())}
                    for eid, e in state.get("events", {}).items()
                    if not e.get("isFinished")
                }
                # Off-time closure — catches races Betway never flags (common for UK/Ireland)
                state["events"] = _close_overdue_races(active)
                if not state["events"]:
                    state = _recover_empty_snapshot(state)
                state["count"] = len(state["events"])
                state["fetch_ok"] = bool(
                    isinstance(betway_state, dict) and betway_state.get("fetch_ok", True)
                )
                state["timestamp"] = datetime.now().isoformat()
                active_ids = list(state["events"].keys())
                active_count = len(active_ids)

                _merge_daily_scan_into(state)
                _atomic_write_json(MARKET_SNAPSHOT_PATH, state)
                # Swarm enrichment: zero-cost field insights for every region without
                # Betway timeForm (USA/Japan/SA/...). Runs inline, never blocks the loop.
                try:
                    enrich_snapshot_with_insights(state)
                except Exception as e:
                    logger.debug(f"Swarm enrichment skipped: {e}")
                try:
                    from core_agent.core.snapshot_cache import set_snapshot, publish_snapshot
                    from core_agent.core.task_queue import get_redis
                    set_snapshot(state)
                    redis_client = await get_redis()
                    await publish_snapshot(redis_client, state)
                except Exception:
                    pass

                # Push snapshot to Cloudflare KV (free, always-on reads for HUD/Telegram)
                try:
                    from core_agent.core.cf_push import push_snapshot
                    await push_snapshot(state)
                except Exception as exc:
                    logger.debug("Cloudflare push skipped: %s", exc)

                # ATR data — per-file, at most every 45 min (see
                # ATR_REFRESH_MIN_GAP_SECS). Fetching every cycle got our egress
                # IPs challenge-walled for 18h on 2026-09-03.
                await self._refresh_atr_feeds(state)

                # Check ATR snapshot staleness and alert if needed
                await self._check_atr_staleness()

                # TTL-based cleanup of old ATR snapshots (keep last 7 days)
                await self._cleanup_atr_snapshots()

                # Update Intelligence Cache for AlertEngine baselines
                for event_id in active_ids:
                    self.intel_cache.update_baseline(
                        event_id, state["events"][event_id].get("runners", [])
                    )

                # Prune old data
                self.intel_cache.prune_stale_data(active_ids)

                logger.info(
                    f"👻 Synchronized {state.get('count')} races ({len(active_ids)} active)."
                )

                # Write healing event for this sync
                _write_healing_event(
                    action="SYNC_COMPLETE",
                    details=f"Synchronized {state.get('count')} races across {len(set(e.get('en','').split(':')[0].strip() for e in state['events'].values()))} regions.",
                    agent="OddsMonitor",
                )

                # 4. Alert Evaluation
                for event in state.get("events", {}).values():
                    await self.alert_engine.evaluate_odds_update(
                        event, cache=self.intel_cache
                    )

            except Exception as e:
                logger.warning(f"⚠️ Sync error: {e}")
                import traceback

                logger.debug(traceback.format_exc())

            # Dynamic sleep — poll aggressively when races are live, back off when idle
            sleep_secs = 15 if active_count > 0 else 300
            logger.debug("Monitor sleep %ds (active_races=%d)", sleep_secs, active_count)
            await asyncio.sleep(sleep_secs)

    async def _check_atr_staleness(self, max_age_hours: int = 3) -> None:
        """Alert if ATR snapshots haven't been updated within max_age_hours."""
        from core_agent.config.paths import ATR_RESULTS_PATH, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH
        import json

        # While the fetch breaker is open the host is blocking us outright, so
        # the snapshots cannot refresh. Alarming on that every 5 minutes is pure
        # noise — the breaker already logged the trip once.
        try:
            from core_agent.skills.parsers.attheraces_api import atr_circuit_open

            if atr_circuit_open():
                logger.debug("ATR staleness check skipped — circuit breaker open")
                return
        except Exception:
            pass

        now = datetime.now()
        stale_alerts = []
        for path, name in [
            (ATR_RESULTS_PATH, "ATR Results"),
            (ATR_MOVERS_PATH, "ATR Market Movers"),
            (ATR_PREDICTOR_PATH, "ATR Predictor"),
        ]:
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    ts_str = data.get("timestamp")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        age_hours = (now - ts).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            stale_alerts.append(f"{name} stale ({age_hours:.1f}h old, last: {ts_str[:19]})")
                    else:
                        stale_alerts.append(f"{name} missing timestamp")
                except Exception:
                    stale_alerts.append(f"{name} unreadable")
            else:
                stale_alerts.append(f"{name} missing file")
        if stale_alerts:
            msg = " | ".join(stale_alerts)
            logger.warning(f"🚨 ATR STALENESS: {msg}")
            try:
                from core_agent.core.alert_engine import AlertEngine
                if not hasattr(self, "_staleness_alerted"):
                    self._staleness_alerted = set()
                alert_key = f"atr_staleness_{hash(msg)}"
                if alert_key not in self._staleness_alerted:
                    self._staleness_alerted.add(alert_key)
                    # Fire a one-time alert via alert engine (non-blocking)
                    from core_agent.core.alert_engine import AlertEngine
                    alert_engine = AlertEngine()
                    await alert_engine._fire_async(
                        "atr_staleness", msg, {"max_age_hours": max_age_hours, "details": stale_alerts}
                    )
            except Exception:
                pass

    async def _cleanup_atr_snapshots(self, ttl_days: int = 7) -> None:
        """Remove ATR snapshot files older than ttl_days (keeps latest, removes backup copies if any)."""
        from core_agent.config.paths import DATA_DIR
        import glob
        from datetime import datetime
        now = datetime.now()
        for pattern in ["atr_*_snapshot.json", "atr_*_snapshot.json.*"]:
            for path_str in glob.glob(str(DATA_DIR / pattern)):
                try:
                    path = Path(path_str)
                    # Keep the main snapshot files
                    if path.name in ["atr_results_snapshot.json", "atr_movers_snapshot.json", "atr_predictor_snapshot.json"]:
                        continue
                    # Remove backup/old copies older than TTL
                    mtime = datetime.fromtimestamp(path.stat().st_mtime)
                    age_days = (now - mtime).days
                    if age_days > ttl_days:
                        path.unlink()
                        logger.info(f"🧹 Cleaned up old ATR snapshot: {path.name} ({age_days}d old)")
                except Exception as e:
                    logger.debug(f"ATR cleanup skipped {path_str}: {e}")

    async def close(self):
        """Clean up resources (digester, etc.)."""
        self.monitoring_active = False
        if self._digester:
            await self._digester.stop()


if __name__ == "__main__":
    monitor = AdaptiveOddsMonitor()
    asyncio.run(monitor.run())
