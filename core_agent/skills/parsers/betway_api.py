import logging
import asyncio
import json
import os
import re
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from .tab4racing import ScrapedRace, ScrapedRunner, _parse_distance_m
from core_agent.core.http_client import get_async_client

logger = logging.getLogger("betway-api")

# One-shot diagnostic: log Betway's own region labels the first time we
# fetch, so the ALLOWED whitelist can be confirmed from production data
# rather than guessed (see the Gulf comment in fetch_racing_data).
_REGION_LABELS_LOGGED = False

# Regions we actually publish. Shared by the direct-fetch path and the KV
# augmentation path so both build the same card.
_ALLOWED_REGIONS = [
    "South Africa",
    "UK and Ireland",
    "Australia",
    "New Zealand",
    "USA",
    "Hong Kong",
    "Japan",
    "France",
    "United Arab Emirates",
    "UAE",
    "Bahrain",
]

# Per-event refresh bookkeeping (Nov-21). Betway's Cloudflare scoring tightens
# as request volume rises, and a 92-race international card re-fetched every
# five minutes is ~1,100 GetEvent calls/hour from one datacenter IP — for races
# that jump hours later. The budget keeps near-off races fresh every cycle and
# lets far-off ones ride, cutting volume ~80% without starving any race.
_REFRESH_STATE_PATH = os.environ.get("BETWAY_REFRESH_STATE") or str(
    Path(__file__).resolve().parents[3] / "data" / "betway_refresh_state.json"
)
_REFRESH_CACHE: Dict[str, float] = {}

# Per-egress-state for the direct -> Worker switch. Modal's cron starts a
# fresh container (and a fresh BetwayAPI) each cycle, so keeping the block
# flag only in memory meant every cycle re-burned direct attempts. Persist it
# on the volume, like the refresh budget.
_EGRESS_STATE_PATH = os.environ.get("BETWAY_EGRESS_STATE") or str(
    Path(__file__).resolve().parents[3] / "data" / "betway_egress_state.json"
)

# Durable last-good price table (Nov-26). Betway's Cloudflare blocks our
# datacentre egress for hours while GetDaily still supplies the race list, so
# every runner collapses to "SP" and the value picks vanish. The fallbacks
# persist their last good table on the volume; Betway prices now do the same so
# a blocked cycle rehydrates the last real price instead of publishing SP.
# Per-race entries expire after 3h so a stale price can never pose as live, and
# a race that fetched even one real price this cycle is left untouched.
BETWAY_PRICE_CACHE_PATH = os.environ.get("BETWAY_PRICE_CACHE") or str(
    Path(__file__).resolve().parents[3] / "data" / "betway_prices_last_good.json"
)
BETWAY_PRICE_CACHE_TTL_SECS = 3 * 3600

_PRICE_CACHE_FIELD_KEYS = (
    "name", "outcomeName", "jockeyName", "trainerName", "form", "timeForm",
    "draw", "age", "weight", "number", "starRating", "imageLocation",
)
_BLANK_FIELD_VALUES = {"", "-", "0", "n/a", "na", "none", "null", "tba", "u", "unknown"}


def _is_priced_odds(odds: Any) -> bool:
    """A real decimal price; ``"SP"``/0/None are unpriced."""
    return (
        isinstance(odds, (int, float))
        and not isinstance(odds, bool)
        and odds > 1.0
    )


def _is_blank_field(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    return str(value).strip().lower() in _BLANK_FIELD_VALUES


def _norm_runner_name(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _event_has_price(event: Any) -> bool:
    return isinstance(event, dict) and any(
        _is_priced_odds(r.get("odds"))
        for r in (event.get("runners") or [])
        if isinstance(r, dict)
    )


def _load_price_cache() -> Tuple[float, Dict[str, Any]]:
    try:
        raw = json.loads(Path(BETWAY_PRICE_CACHE_PATH).read_text())
    except Exception:
        return 0.0, {}
    if not isinstance(raw, dict):
        return 0.0, {}
    events = raw.get("events")
    try:
        ts = float(raw.get("ts") or 0.0)
    except Exception:
        ts = 0.0
    return ts, events if isinstance(events, dict) else {}


def _save_price_cache(events: Dict[str, Any]) -> None:
    """Union this cycle's priced races into the on-disk table.

    Only priced races are stored. A race that came back all-SP keeps its
    previous entry until the TTL drops it, so one blocked cycle cannot erase
    the only real price we have. Accepts either the events dict or a whole
    snapshot wrapper so a caller passing ``get_snapshot_format``'s output
    cannot silently persist nothing.
    """
    if isinstance(events, dict) and isinstance(events.get("events"), dict):
        events = events["events"]
    now = time.time()
    _, prev = _load_price_cache()
    merged: Dict[str, Any] = {
        str(k): v for k, v in prev.items() if isinstance(v, dict)
    }
    for eid, event in (events or {}).items():
        if not _event_has_price(event):
            continue
        merged[str(eid)] = {
            "course": event.get("course"),
            "raceNumber": event.get("raceNumber"),
            "runners": [
                {key: r.get(key) for key in _PRICE_CACHE_FIELD_KEYS}
                | {
                    "odds": r.get("odds"),
                    "price_source": r.get("price_source") or event.get("price_source"),
                    "non_runner": bool(r.get("non_runner")),
                }
                for r in (event.get("runners") or [])
                if isinstance(r, dict)
            ],
            "cached_at": now,
        }
    merged = {
        k: v for k, v in merged.items()
        if now - float((v or {}).get("cached_at") or 0.0) < BETWAY_PRICE_CACHE_TTL_SECS
    }
    try:
        path = Path(BETWAY_PRICE_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w") as f:
            json.dump({"ts": now, "events": merged}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001 - cache write is best effort
        logger.debug("Betway price cache write skipped: %s", exc)


def _apply_price_cache(out: Dict[str, Any]) -> Dict[str, Any]:
    """Persist priced races, and rehydrate races that arrived unpriced.

    Per-race, not whole-card: a cycle that priced only one meeting must still
    get the other meetings' last good prices, and a race that returned a real
    price must keep it (the cache can never mask a live move).
    """
    events = out.get("events")
    if not isinstance(events, dict) or not events:
        return out

    if any(_event_has_price(ev) for ev in events.values()):
        _save_price_cache(events)

    _, cached = _load_price_cache()
    if not cached:
        return out

    now = time.time()
    restored = 0
    filled = 0
    touched = 0
    for eid, event in events.items():
        if _event_has_price(event):
            continue
        entry = cached.get(str(eid))
        if not isinstance(entry, dict):
            continue
        try:
            entry_age = now - float(entry.get("cached_at") or 0.0)
        except Exception:
            entry_age = float("inf")
        if entry_age >= BETWAY_PRICE_CACHE_TTL_SECS:
            continue
        prev_by_name = {
            _norm_runner_name(r.get("name") or r.get("outcomeName")): r
            for r in (entry.get("runners") or [])
            if isinstance(r, dict)
        }
        changed = False
        for runner in (event.get("runners") or []):
            if not isinstance(runner, dict) or runner.get("non_runner"):
                continue
            prev_runner = prev_by_name.get(
                _norm_runner_name(runner.get("name") or runner.get("outcomeName"))
            )
            if not prev_runner:
                continue
            if not _is_priced_odds(runner.get("odds")) and _is_priced_odds(prev_runner.get("odds")):
                runner["odds"] = prev_runner["odds"]
                runner["price_source"] = prev_runner.get("price_source") or "cache"
                runner["price_cached"] = True
                restored += 1
                changed = True
            for key in _PRICE_CACHE_FIELD_KEYS:
                if key in ("name", "outcomeName"):
                    continue
                if _is_blank_field(runner.get(key)) and not _is_blank_field(prev_runner.get(key)):
                    runner[key] = prev_runner[key]
                    filled += 1
                    changed = True
        if changed:
            touched += 1

    if restored or filled:
        out["price_cache_used"] = True
        out["price_cache_restored"] = restored
        # Every event in this card was unpriced, so the daily count is no
        # longer accurate once the cache fills it.
        if out.get("daily_unpriced"):
            out["daily_unpriced"] = 0
        logger.info(
            "Betway price cache: restored %d price(s) and %d field(s) across "
            "%d race(s)",
            restored,
            filled,
            touched,
        )
    return out


def _classify_html_block(body: str) -> str:
    """Name the layer behind an HTML error page.

    A 403 with an HTML body never came from the API — a WAF answered instead.
    Betway and ``*.workers.dev`` are both fronted by Cloudflare, so the same
    page can mean "Betway refused us" or "Cloudflare refused Modal"; only the
    page itself tells them apart. BeautifulSoup is used purely for that: there
    is no race data in a block page to parse.
    """
    head = (body or "")[:5000]
    title = ""
    try:
        from bs4 import BeautifulSoup

        parsed = BeautifulSoup(head, "html.parser")
        title = (parsed.title.get_text(strip=True) if parsed.title else "")
    except Exception:
        title = ""
    low = head.lower()
    if "error code: 52" in low:
        return "Cloudflare origin error (520/522 — not a block)"
    if "attention required" in title.lower() or "attention required" in low:
        return "Cloudflare WAF block page"
    if "just a moment" in title.lower() or "just a moment" in low:
        return "Cloudflare JS challenge"
    if title:
        return f"HTML error page ({title[:60]})"
    return "HTML error page"


def _load_egress_state() -> Dict[str, Any]:
    """Read the egress switch state; missing/corrupt means 'direct is fine'."""
    try:
        raw = json.loads(Path(_EGRESS_STATE_PATH).read_text())
    except Exception:
        return {"blocked": False, "cycles_since_probe": 0, "failures": 0}
    if not isinstance(raw, dict):
        return {"blocked": False, "cycles_since_probe": 0, "failures": 0}
    try:
        return {
            "blocked": bool(raw.get("blocked", False)),
            "cycles_since_probe": max(0, int(raw.get("cycles_since_probe") or 0)),
            "failures": max(0, int(raw.get("failures") or 0)),
        }
    except Exception:
        return {"blocked": False, "cycles_since_probe": 0, "failures": 0}


def _save_egress_state(state: Dict[str, Any]) -> None:
    """Best effort: a read-only volume just means we fall back to per-cycle."""
    try:
        path = Path(_EGRESS_STATE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "blocked": bool(state.get("blocked")),
            "cycles_since_probe": int(state.get("cycles_since_probe") or 0),
            "failures": int(state.get("failures") or 0),
        }))
    except Exception as exc:  # pragma: no cover - read-only/absent volume
        logger.debug("Egress switch state not persisted: %s", exc)


# Last good GetDaily card. GetDaily is the gate for the whole cycle: when it
# 403/520s, no GetEvent call runs at all and races that became near-off during
# the outage are never refreshed. Keeping the event-id list on the volume lets
# us still fetch the near-off races from the last known card.
_DAILY_CACHE_PATH = os.environ.get("BETWAY_DAILY_CACHE") or str(
    Path(__file__).resolve().parents[3] / "data" / "betway_daily_cache.json"
)
_DAILY_CACHE_MAX_AGE_SECS = 6 * 3600


def _save_daily_cache(payload: Dict[str, Any]) -> None:
    try:
        path = Path(_DAILY_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": time.time(), "payload": payload}))
    except Exception as exc:  # pragma: no cover - read-only volume
        logger.debug("GetDaily cache write skipped: %s", exc)


def _load_daily_cache() -> Optional[Dict[str, Any]]:
    """Last known card, or None when absent, corrupt or too old to trust."""
    try:
        blob = json.loads(Path(_DAILY_CACHE_PATH).read_text())
    except Exception:
        return None
    if not isinstance(blob, dict):
        return None
    if time.time() - float(blob.get("ts") or 0) > _DAILY_CACHE_MAX_AGE_SECS:
        return None
    payload = blob.get("payload")
    return payload if isinstance(payload, dict) and payload.get("regions") else None


def _load_refresh_state() -> Dict[str, float]:
    """Last-successful-fetch epoch per event id (disk-backed, best effort).

    Modal cron containers are not guaranteed to stay warm between cycles, so
    the budget state is persisted. An unreadable/absent file just means "no
    budget yet" — every event is fetched once, which is the safe default.
    """
    if _REFRESH_CACHE:
        return _REFRESH_CACHE
    try:
        raw = json.loads(Path(_REFRESH_STATE_PATH).read_text())
    except Exception:
        return _REFRESH_CACHE
    if isinstance(raw, dict):
        _REFRESH_CACHE.update(
            {str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))}
        )
    return _REFRESH_CACHE


def _save_refresh_state(state: Dict[str, float], now: float) -> None:
    """Persist the budget state, dropping entries older than a day."""
    fresh = {k: v for k, v in state.items() if now - v < 86400}
    if len(fresh) > 2000:  # hard cap: yesterday's card can't grow unbounded
        freshest = sorted(fresh.items(), key=lambda kv: kv[1], reverse=True)[:2000]
        fresh = dict(freshest)
    _REFRESH_CACHE.clear()
    _REFRESH_CACHE.update(fresh)
    try:
        path = Path(_REFRESH_STATE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fresh))
    except Exception as exc:  # pragma: no cover - read-only/absent volume
        logger.debug("Refresh budget state not persisted: %s", exc)



def _details_from_daily(
    data: Dict[str, Any],
    have_ids: set,
    allowed_regions: List[str],
) -> List[Dict[str, Any]]:
    """Build price-less event details straight from GetDaily.

    Chrome DevTools on the live site (2026-11-23) shows Betway still calls the
    same ``TrackRacing/GetDaily`` + ``GetEvent`` endpoints with the same query
    strings — the API did not change. What GetDaily *does* carry is
    ``raceEventDetails.racers`` (157 events / 1,410 runners today): the full
    field with numbers, jockey, trainer, form and weight.

    Only prices live in GetEvent. So when GetEvent is refused by the WAF we can
    still publish every live race from one GetDaily call and mark it unpriced,
    instead of dropping the race and hammering Betway with retries.
    """
    out: List[Dict[str, Any]] = []
    have = {str(x) for x in have_ids}
    for reg in data.get("regions", []) or []:
        reg_name = str(reg.get("name") or "")
        if not any(a in reg_name for a in allowed_regions):
            continue
        for event in reg.get("sportEvents", []) or []:
            if not isinstance(event, dict) or event.get("isFinished"):
                continue
            eid = event.get("eventId")
            if eid is None or str(eid) in have:
                continue
            racers = (event.get("raceEventDetails") or {}).get("racers") or []
            out.append({
                "eventId": eid,
                "regionName": reg_name,
                "leagueName": (event.get("league") or "").strip(),
                "result": {
                    "events": [event],
                    "outcomes": [],
                    "markets": [],
                    "prices": [],
                },
                "price_source": "daily",
                # US cards publish their field late: the race is real and
                # scheduled, it just has no runners yet. Keep the slot so the
                # HUD shows EVALUATING instead of hiding the race entirely.
                "field_pending": not racers,
            })
    return out


def daily_event_ids(max_age_seconds: float = _DAILY_CACHE_MAX_AGE_SECS) -> set:
    """Event ids on today's authoritative GetDaily card ({} when unavailable).

    GetDaily is the only source that says what races exist *today*. Carry-forward
    and the registry restore by id, and ``t`` has no date, so a Saturday race can
    re-anchor to Monday's clock and look upcoming forever. Anything absent from a
    fresh GetDaily is yesterday's card and must go.

    Uses the same trust window as the parser's own daily cache, and refuses a
    cache stamped on a previous UTC day — yesterday's list must never prune
    today's card. Returns an empty set when unavailable, which disables the gate.
    """
    try:
        blob = json.loads(Path(_DAILY_CACHE_PATH).read_text())
    except Exception:
        return set()
    if not isinstance(blob, dict):
        return set()
    try:
        ts = float(blob.get("ts") or 0)
    except (TypeError, ValueError):
        return set()
    if not ts or time.time() - ts > max_age_seconds:
        return set()
    if (
        datetime.fromtimestamp(ts, timezone.utc).date()
        != datetime.now(timezone.utc).date()
    ):
        return set()
    data = blob.get("payload")
    if not isinstance(data, dict):
        return set()
    ids: set = set()
    for reg in data.get("regions", []) or []:
        for event in reg.get("sportEvents", []) or []:
            eid = event.get("eventId") if isinstance(event, dict) else None
            if eid is None:
                continue
            try:
                ids.add(int(eid))
            except (TypeError, ValueError):
                continue
    return ids


class BetwayAPI:
    BASE_URL = "https://www.betway.co.za/sportsapi/v1/TrackRacing"

    # Retry ladder for the probabilistic 403. Three things matter here:
    #
    # 1. The block is per browser fingerprint, so a *fresh session* each
    #    attempt is what clears it (see fetch_racing_data).
    # 2. The failures arrive in waves, not independently. Nov-2026 production
    #    had 166 in two days, clustered in the 03:00-07:00 UTC window when the
    #    international cards load, and 26 poll cycles returned zero races.
    #    With four attempts at a ~29% per-attempt failure rate we would expect
    #    ~0.7% total failure, but 4.5% was observed — proof the failures
    #    correlate. Retrying inside the same wave needs *time*, not just
    #    another fingerprint.
    # 3. The whole ladder still has to fit inside the 5-minute poll, so a
    #    total budget (not just a per-sleep cap) bounds the damage.
    MAX_ATTEMPTS = 5
    BACKOFF_SECONDS = (3.0, 9.0, 24.0, 45.0)
    RETRY_BUDGET_SECONDS = 150.0

    # Refresh budget (Nov-21). Near-off races must be current — a punter bets
    # minutes before the jump. Far-off races only need to be *known*, and the
    # snapshot's carry-forward keeps their last price on the card meanwhile.
    NEAR_OFF_WINDOW_SECONDS = 90 * 60
    FAR_REFRESH_SECONDS = 25 * 60
    FULL_SWEEP_SECONDS = 60 * 60

    # Per-event retry. Betway's GetEvent flaps in waves (Nov-21: 520 from
    # Cloudflare "origin unreachable" for minutes at a time, then 200 again),
    # and a single failed call used to cost a race its place on the card for a
    # whole cycle. One bounded second pass rides the flap out.
    EVENT_RETRY_DELAY_SECONDS = 6.0
    EVENT_RETRY_MAX = 60

    # Bounded direct -> Worker switch (Nov-21). 7f11c91 removed the sticky
    # proxy mode, so every one of ~200 GetEvent calls per cycle first hit the
    # blocked Modal IP, and the failure rate went 4.5% -> 48% -> 91%. Two
    # failed direct GetDaily attempts in a cycle mark this egress as blocked
    # for that cycle; a single direct probe per hour checks for recovery.
    DIRECT_FAILURE_THRESHOLD = 2
    DIRECT_PROBE_EVERY_CYCLES = 12

    # One browser for the whole cycle (Nov-24). _http_get used to build a fresh
    # client per call and get_impersonate() picked randomly, so a single cycle
    # fired ~83 GetEvent requests carrying up to 83 different TLS fingerprints
    # from one IP in ten seconds. No browser does that; the rotation was a bot
    # signature in its own right, independent of which profile is "best".
    IMPERSONATE = "chrome131"

    # The User-Agent that IMPERSONATE sends. The Worker-proxy path used to
    # advertise a Windows Chrome while the direct path advertised a macOS one,
    # so the same source looked like two different machines.
    BROWSER_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        saved = _load_egress_state()
        self._direct_blocked = bool(saved["blocked"])
        self._cycles_since_probe = int(saved["cycles_since_probe"])
        self._direct_failures = int(saved["failures"])
        self._probe_direct_this_cycle = not self._direct_blocked
        # Edge-block diagnostics: one accurate line per cycle, not one per call.
        self._edge_blocked_calls = 0
        self._edge_block_logged = False
        # Reused for every direct call in a cycle, then dropped by start_cycle.
        self._cycle_client = None

    def _client(self):
        """One pinned-fingerprint client per cycle, reused across calls.

        Reuse keeps a single TLS session and connection pool, which is both
        cheaper and less anomalous than a new handshake per event.
        """
        if self._cycle_client is None:
            self._cycle_client = get_async_client(
                timeout=90.0,
                no_proxy=True,
                impersonate=self.IMPERSONATE,
                resolve_hosts={"www.betway.co.za"},
            )
        return self._cycle_client

    def _clear_cycle_cookies(self) -> None:
        """Empty the cookie jar after a refused call, keeping the connection.

        Cloudflare hands out a ``__cf_bm`` token on every 200 and scores it per
        session. A 403 can arrive with that token marked, and re-sending it
        would carry the mark for every later call in the cycle. Before 9fe97cf
        each call built its own client, so no jar ever survived a request and
        the question could not arise; now one cycle shares a jar, so the jar has
        to be emptied when a call is refused.
        """
        client = self._cycle_client
        if client is None:
            return
        try:
            client.cookies.clear()
        except Exception:  # pragma: no cover - fall back to a new session
            self._drop_cycle_client()

    def _drop_cycle_client(self) -> None:
        """Release last cycle's client without blocking a sync caller."""
        client, self._cycle_client = self._cycle_client, None
        if client is None:
            return
        try:
            import asyncio

            asyncio.get_running_loop().create_task(client.close())
        except Exception:  # pragma: no cover - no loop / already closed
            pass

    def _persist_egress(self) -> None:
        _save_egress_state({
            "blocked": self._direct_blocked,
            "cycles_since_probe": self._cycles_since_probe,
            "failures": self._direct_failures,
        })

    def start_cycle(self) -> None:
        """Decide whether this cycle probes the (possibly blocked) direct IP.

        Re-reads the volume first: each Modal cron cycle is a new container,
        so a sibling container may have blocked or unblocked since our init.
        The failure count deliberately persists across cycles — when the proxy
        answers, the cycle succeeds on its first attempt, so waiting for two
        failures inside one cycle would never trip the switch.
        """
        saved = _load_egress_state()
        self._direct_blocked = bool(saved["blocked"])
        self._cycles_since_probe = int(saved["cycles_since_probe"])
        self._direct_failures = int(saved["failures"])
        self._edge_blocked_calls = 0
        self._edge_block_logged = False
        self._drop_cycle_client()
        if not self._direct_blocked:
            self._probe_direct_this_cycle = True
        elif self._cycles_since_probe >= self.DIRECT_PROBE_EVERY_CYCLES:
            self._probe_direct_this_cycle = True
            self._cycles_since_probe = 0
        else:
            self._probe_direct_this_cycle = False
            self._cycles_since_probe += 1
        self._persist_egress()

    def _should_try_direct(self, path: str) -> bool:
        """Post-block, only GetDaily probes direct — never 200 GetEvents."""
        if not self._direct_blocked:
            return True
        return self._probe_direct_this_cycle and path == "GetDaily"

    def _note_direct_result(self, path: str, ok: bool) -> None:
        """Update the egress switch from a direct attempt's outcome."""
        if ok:
            if not self._direct_blocked and not self._direct_failures:
                return  # nothing changed — don't write on every event
            self._direct_blocked = False
            self._direct_failures = 0
            self._cycles_since_probe = 0
            self._persist_egress()
            return
        if path != "GetDaily" or self._direct_blocked:
            return  # per-event 520s are Betway's origin, not our IP being blocked
        self._direct_failures += 1
        if self._direct_failures >= self.DIRECT_FAILURE_THRESHOLD:
            self._direct_blocked = True
            self._probe_direct_this_cycle = False
            logger.warning(
                "Betway direct egress blocked (%d GetDaily failures) — "
                "remaining %s calls via Worker only",
                self._direct_failures, path,
            )
        self._persist_egress()

    def _select_events(
        self,
        event_ids: List[Tuple[Any, Any, Any, Any]],
        state: Dict[str, float],
        now: float,
    ) -> Tuple[List[Tuple[Any, Any, Any, Any]], int, bool]:
        """Split the card into (events to fetch, skipped count, full_sweep).

        Fetch when *any* of these hold:
          - the hourly full sweep is due (nothing is ever starved);
          - the race jumps within ``NEAR_OFF_WINDOW_SECONDS`` (or has no start
            time — unknown is always refreshed);
          - it has never been fetched, or not for ``FAR_REFRESH_SECONDS``.

        Everything else rides on the price already in the snapshot.
        """
        last_sweep = state.get("_last_sweep", 0.0)
        full_sweep = (now - last_sweep) >= self.FULL_SWEEP_SECONDS
        if full_sweep:
            return list(event_ids), 0, True

        to_fetch: List[Tuple[Any, Any, Any, Any]] = []
        for item in event_ids:
            eid, start = item[0], item[3] or 0
            last = state.get(str(eid), 0.0)
            near_off = start > 0 and (start - now) <= self.NEAR_OFF_WINDOW_SECONDS
            if near_off or start <= 0 or not last or (now - last) >= self.FAR_REFRESH_SECONDS:
                to_fetch.append(item)

        # Never return an empty batch: a card of only far-off races that were
        # refreshed recently would otherwise look like a failed fetch upstream.
        if not to_fetch:
            return list(event_ids), 0, True

        return to_fetch, len(event_ids) - len(to_fetch), False

    def _worker_config(self):
        import os
        url = (os.environ.get("CLOUDFLARE_MCP_URL", "") or "").rstrip("/") or "https://striketips-mcp.gmphorg379.workers.dev"
        key = (
            os.environ.get("STRIKE_TIPS_API_KEY", "")
            or os.environ.get("BACKEND_API_KEY", "")
            or os.environ.get("CLOUDFLARE_API_KEY", "")
        )
        return url, key

    # ── Cloudflare-side fetch (Nov-22) ───────────────────────────────
    # Modal's Azure egress is refused by Betway's WAF on the API *and* the
    # racecard HTML (403 "Attention Required! | Cloudflare"), and Modal ->
    # *.workers.dev is refused per Cloudflare colo (BOM/SIN 403, AMS 200).
    # Cloudflare's own egress is what Betway accepts, so a Worker cron parks
    # raw GetEvent payloads in KV and this reads them back over
    # api.cloudflare.com — a hostname Modal can reach.
    # Nov-22: raised from 15 min to 60 min. A Betway block can outlast 15 min,
    # and throwing away the last-good card blanked the HUD (0 races at 10:41).
    # The quiet chip still says "Prices out of date · last update Xm ago", so
    # the age is visible — we just no longer self-destruct a good card.
    EDGE_KV_MAX_AGE_SECONDS = 60 * 60
    EDGE_KV_SLOTS = 16

    @staticmethod
    def _iso_age_seconds(value: Any) -> Optional[float]:
        if not isinstance(value, str):
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds()
        except Exception:
            return None

    async def fetch_from_edge_kv(
        self, max_age_seconds: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Assemble races from the raw payloads parked in KV.

        The default 60-minute cutoff decides whether a batch is "live". A
        caller can widen it to reuse last-good *prices* while GetDaily supplies
        the current race list — stale prices beat no prices at all, and the
        card's daily gate + closer still drop finished races.
        """
        from core_agent.core import cf_kv

        if not cf_kv.configured():
            return None

        details: List[Dict[str, Any]] = []
        seen: set = set()
        newest_age: Optional[float] = None
        oldest_age: Optional[float] = None

        # Modal-written slots first: they are the newest successful fetch.
        # Cron slots are the fallback when Modal has not fetched in a while.
        sources = [f"{cf_kv.MODAL_RAW_PREFIX}{i}" for i in range(self.EDGE_KV_SLOTS)]
        sources += [f"betway:raw:slot:{i}" for i in range(self.EDGE_KV_SLOTS)]
        for key in sources:
            payload = await cf_kv.kv_get_json(key)
            if not isinstance(payload, dict):
                continue
            events = payload.get("events")
            if not isinstance(events, dict):
                continue
            age = self._iso_age_seconds(payload.get("ts"))
            if age is not None:
                newest_age = age if newest_age is None else min(newest_age, age)
                oldest_age = age if oldest_age is None else max(oldest_age, age)
            for eid, entry in events.items():
                if eid in seen or not isinstance(entry, dict):
                    continue
                det = entry.get("payload")
                if not isinstance(det, dict):
                    continue
                det = dict(det)
                det["eventId"] = eid
                det["regionName"] = entry.get("region") or "Unknown"
                det["leagueName"] = entry.get("league") or "Unknown"
                det["_edge_age_secs"] = age
                details.append(det)
                seen.add(eid)

        if not details:
            return None
        cutoff = (
            self.EDGE_KV_MAX_AGE_SECONDS
            if max_age_seconds is None
            else max_age_seconds
        )
        if newest_age is not None and newest_age > cutoff:
            logger.warning(
                "Edge KV batch %.0fs old exceeds %.0fs cutoff — skipped",
                newest_age, cutoff,
            )
            return None
        stale = bool(
            newest_age is not None
            and newest_age > self.EDGE_KV_MAX_AGE_SECONDS
        )
        if stale:
            logger.info(
                "Edge KV last-good prices: newest batch %.0fs old", newest_age
            )

        logger.info(
            "Edge KV supplied %d race(s) (newest %.0fs, oldest %.0fs)",
            len(details), newest_age or 0, oldest_age or 0,
        )
        return {
            "status": "success",
            "details": details,
            "daily_from_cache": False,
            "edge_kv": True,
            "edge_newest_age_secs": newest_age,
            "edge_oldest_age_secs": oldest_age,
            "edge_stale": stale,
        }

    async def _http_get(self, path: str, qs: str, headers: dict) -> Optional[Dict[str, Any]]:
        """Fetch a Betway TrackRacing endpoint, falling back to the Worker proxy.

        Returns parsed JSON on success, None on failure (so callers can retry).
        """
        # 1. Try direct fetch (curl_cffi with fresh session and browser fingerprint).
        # Skipped entirely for GetEvent once this egress is known to be blocked.
        if self._should_try_direct(path):
            try:
                client = self._client()
                url = f"{self.BASE_URL}/{path}?{qs}"
                resp = await client.get(url, headers=headers)
                status = getattr(resp, "status_code", None)
                if status == 200 or status is None:
                    try:
                        if hasattr(resp, "raise_for_status"):
                            resp.raise_for_status()
                        payload = resp.json()
                        self._note_direct_result(path, True)
                        return payload
                    except Exception as e:
                        self._note_direct_result(path, False)
                        logger.debug("Betway direct parse failed on %s: %s", path, e)
                else:
                    self._note_direct_result(path, False)
                    self._clear_cycle_cookies()
                    logger.debug("Betway direct fetch HTTP %s on %s — attempting Worker proxy", status, path)
            except Exception as e:
                self._note_direct_result(path, False)
                self._clear_cycle_cookies()
                logger.debug("Betway direct fetch failed on %s: %s — attempting Worker proxy", path, e)

        # 2. Worker proxy fallback (Cloudflare edge IPs bypass datacenter IP blocks)
        url, key = self._worker_config()
        if key:
            try:
                import httpx
                worker_headers = {
                    "x-api-key": key,
                    "User-Agent": self.BROWSER_UA,
                }
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.get(
                        f"{url}/api/fetch-betway",
                        params={"path": path, "qs": qs},
                        headers=worker_headers,
                    )
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        pass
                # An HTML body means a WAF answered, not Betway. Say which one
                # once per cycle instead of blaming Betway on all ~200 calls.
                if "<html" in resp.text[:400].lower():
                    reason = _classify_html_block(resp.text)
                    self._edge_blocked_calls += 1
                    if not self._edge_block_logged:
                        self._edge_block_logged = True
                        logger.warning(
                            "Worker edge refused this cycle (%d %s): Modal cannot reach "
                            "*.workers.dev from this colo — this is Cloudflare blocking Modal, "
                            "not a Betway response. %d call(s) affected; the Worker cron + "
                            "edge KV path is the production fetch.",
                            resp.status_code, reason, self._edge_blocked_calls,
                        )
                else:
                    logger.warning(
                        "Worker proxy %s returned %d: %.120s", path, resp.status_code, resp.text
                    )
            except Exception as e:
                logger.debug("Worker proxy failed on %s: %s", path, e)

        return None

    def _augment_edge_with_daily(self, edge: Dict[str, Any]) -> None:
        """Add today's unpriced GetDaily races to an edge-KV result.

        The KV bridge returns only races whose GetEvent once answered, so on a
        blocked morning it carried 45 races while GetDaily listed 64 — the rest
        were simply absent from the HUD. GetDaily is authoritative for which
        races exist today, so fold in its price-less rows (same gate as the
        direct path) and hand the id list to the card's daily gate.
        """
        if not isinstance(edge, dict) or not isinstance(edge.get("details"), list):
            return
        ids = daily_event_ids()
        if not ids:
            return
        data = _load_daily_cache()
        if not isinstance(data, dict):
            return
        have_ids = {str(d.get("eventId")) for d in edge["details"]}
        details = _details_from_daily(data, have_ids, _ALLOWED_REGIONS)
        if details:
            edge["details"] = edge["details"] + details
            edge["daily_unpriced"] = len(details)
            edge["daily_ids"] = sorted(ids)
            logger.info(
                "Edge KV + GetDaily: %d cached races, %d unpriced additions",
                len(have_ids), len(details),
            )
        else:
            # Still pass the id list so today's gate can prune yesterday's rows.
            edge.setdefault("daily_ids", sorted(ids))


    async def fetch_racing_data(self) -> Dict[str, Any]:
        """Fetch raw racing data from Betway's TrackRacing (TAB) API.

        Betway's bot management rejects the rotating ``SCRAPER_PROXIES`` pool
        (403 on every attempt, proven in the 2026-11-04 logs while the same
        request succeeded direct) but accepts direct curl_cffi impersonation,
        so this source bypasses the proxy pool. A fresh session per attempt
        gives a clean cookie jar and a new browser fingerprint, which is what
        clears the probabilistic 403.
        """
        bw_headers = {
            "Referer": "https://www.betway.co.za/sport/horse-racing",
            "Origin": "https://www.betway.co.za",
        }
        self.start_cycle()

        # Cloudflare-side fetch first: it is the only egress Betway accepts.
        # Reuse KV prices for up to 3h (the slot TTL): GetDaily still supplies
        # today's race list, so an older batch can only contribute prices.
        edge = await self.fetch_from_edge_kv(max_age_seconds=3 * 3600)
        if edge is not None:
            # The KV cache holds priced races only. Still fold in today's
            # GetDaily field so races whose GetEvent never landed are present
            # (price-less) rather than silently missing from the card.
            self._augment_edge_with_daily(edge)
            return edge

        started = time.monotonic()
        last_error: Optional[BaseException] = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                daily_qs = "sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2"
                data = await self._http_get("GetDaily", daily_qs, bw_headers)
                daily_from_cache = False
                if data is None:
                    data = _load_daily_cache()
                    daily_from_cache = data is not None
                if data is None:
                    raise RuntimeError("Betway GetDaily returned no data (direct + proxy both failed)")
                if not daily_from_cache:
                    _save_daily_cache(data)
                # Ids from the payload actually fetched THIS cycle. Passing
                # these to the card's daily gate avoids pruning against a
                # hours-old cache that predates the evening cards.
                fresh_daily_ids = sorted({
                    int(e["eventId"])
                    for reg in data.get("regions", []) or []
                    for e in (reg.get("sportEvents") or [])
                    if isinstance(e, dict) and e.get("eventId") is not None
                }) if not daily_from_cache else []

                event_ids = []
                ALLOWED = _ALLOWED_REGIONS

                # Learn Betway's real region labels from production instead of
                # guessing: the probe path is 403'd (per-IP fingerprint) but
                # this runs on the same direct fetch the live monitor uses.
                # Logged once per process, so it costs nothing per poll.
                global _REGION_LABELS_LOGGED
                if not _REGION_LABELS_LOGGED:
                    _REGION_LABELS_LOGGED = True
                    logger.info(
                        "Betway regions: %s",
                        sorted(
                            str(r.get("name") or "") for r in data.get("regions", [])
                        ),
                    )

                for reg in data.get("regions", []):
                    if not any(a in reg.get("name", "") for a in ALLOWED):
                        continue
                    for e in reg.get("sportEvents", []):
                        if not e.get("isFinished", True):
                            event_ids.append(
                                (
                                    e["eventId"],
                                    reg.get("name"),
                                    (e.get("league") or "").strip(),
                                    e.get("expectedStartEpoch") or 0,
                                )
                            )

                # Prioritize South African meetings first, then by earliest start time
                event_ids.sort(
                    key=lambda x: (
                        0 if "South Africa" in str(x[1]) else 1,
                        x[3] if x[3] > 0 else 9999999999,
                    )
                )

                # Refresh budget: near-off races every cycle, far-off ones at
                # most every FAR_REFRESH_SECONDS, full sweep hourly. Cuts the
                # per-cycle GetEvent volume that feeds Betway's bot score.
                budget_state = _load_refresh_state()
                now_epoch = time.time()
                if daily_from_cache:
                    # GetDaily is down. Only the near-off races matter right
                    # now, and a full sweep here would hammer Betway with the
                    # entire card on top of the failed gate.
                    to_fetch = [
                        x for x in event_ids
                        if x[3] > 0 and (x[3] - now_epoch) <= self.NEAR_OFF_WINDOW_SECONDS
                    ]
                    skipped = 0
                    full_sweep = False
                    if not to_fetch:
                        raise RuntimeError(
                            "Betway GetDaily failed and the cached card has no near-off races"
                        )
                    logger.warning(
                        "Betway GetDaily failed — using cached card for %d near-off race(s)",
                        len(to_fetch),
                    )
                else:
                    to_fetch, skipped, full_sweep = self._select_events(
                        event_ids, budget_state, now_epoch
                    )
                    if skipped:
                        logger.info(
                            "Refresh budget: fetching %d/%d events (%d far-off skipped)",
                            len(to_fetch), len(event_ids), skipped,
                        )
                    elif full_sweep and event_ids:
                        logger.info("Refresh budget: full sweep of %d events", len(event_ids))

                # Throttle to max 4 concurrent requests with gentle jitter to avoid
                # tripping Betway's Cloudflare rate limiter
                sem = asyncio.Semaphore(4)
                # One pinned-fingerprint client for the whole burst: the same
                # browser for every event, not 80 different ones.
                client = self._client()
                tasks = [
                    self._fetch_event_safe(client, eid, reg_name, league, sem)
                    for eid, reg_name, league, _ in to_fetch
                ]

                events_details = await asyncio.gather(*tasks)
                events_details = [e for e in events_details if e]

                # One bounded second pass over races that failed. Betway's
                # GetEvent flaps in waves (520 from Cloudflare, 403 challenge)
                # that often clear within seconds; without this, one failed
                # call costs a race its slot for the whole cycle, which is how
                # a 9-race meeting ended up with 2 on the card.
                got_ids = {d.get("eventId") for d in events_details}
                retry_items = [item for item in to_fetch if item[0] not in got_ids]
                if (
                    retry_items
                    and len(retry_items) < len(to_fetch)  # never double a total outage
                    and len(retry_items) <= self.EVENT_RETRY_MAX
                ):
                    await asyncio.sleep(self.EVENT_RETRY_DELAY_SECONDS)
                    retry_tasks = [
                        self._fetch_event_safe(client, eid, reg_name, league, sem)
                        for eid, reg_name, league, _ in retry_items
                    ]
                    retry_details = await asyncio.gather(*retry_tasks)
                    recovered = [e for e in retry_details if e]
                    events_details.extend(recovered)
                    if recovered:
                        logger.info(
                            "Betway GetEvent second pass recovered %d/%d race(s)",
                            len(recovered), len(retry_items),
                        )

                # Remember what actually answered, so a failed event is retried
                # next cycle instead of being parked for FAR_REFRESH_SECONDS.
                for detail in events_details:
                    fetched_id = detail.get("eventId")
                    if fetched_id is not None:
                        budget_state[str(fetched_id)] = now_epoch
                if full_sweep:
                    budget_state["_last_sweep"] = now_epoch
                _save_refresh_state(budget_state, now_epoch)

                # GetDaily carries the full field (raceEventDetails.racers), so
                # a race whose GetEvent was refused still belongs on the card —
                # unpriced, not absent. This is what turns a 403 wave from
                # "14 races" into "every live race" without extra requests.
                have_ids = {str(d.get("eventId")) for d in events_details}
                daily_details = _details_from_daily(data, have_ids, ALLOWED)
                if daily_details:
                    events_details.extend(daily_details)
                    logger.info(
                        "GetDaily supplied %d unpriced race(s) whose GetEvent was refused",
                        len(daily_details),
                    )

                # GetDaily answered with events but every per-event call failed:
                # a bot-blocked wave, not a dark day. Return an error so the HUD
                # says the feed is broken instead of showing an empty card.
                if to_fetch and not events_details:
                    raise RuntimeError(
                        f"Betway GetDaily returned {len(to_fetch)} events but "
                        "all per-event GetEvent calls failed"
                    )

                # Keep a cross-colo last-good cache in KV. The next cycle may
                # land in a colo Betway refuses; KV is reachable from every
                # colo over the REST API, so the card survives that wave.
                # Price-less GetDaily rows are never parked: the cache exists to
                # carry *prices* across colos, not to dilute them with SP rows.
                try:
                    from core_agent.core import cf_kv

                    parkable = [
                        d for d in events_details if d.get("price_source") != "daily"
                    ]
                    parked = await cf_kv.put_details(parkable) if parkable else 0
                    if parked:
                        logger.info(
                            "Edge KV cache: parked %d race(s) in %d slot(s)",
                            len(events_details), parked,
                        )
                except Exception as exc:  # pragma: no cover - best effort
                    logger.debug("Edge KV cache write skipped: %s", exc)

                return {
                    "status": "success",
                    "details": events_details,
                    "daily_from_cache": daily_from_cache,
                    "daily_unpriced": len(daily_details),
                    "daily_ids": fresh_daily_ids,
                }
            except Exception as e:
                last_error = e
                attempts_used = attempt + 1
                if attempts_used >= self.MAX_ATTEMPTS:
                    logger.warning(
                        "Betway fetch gave up after %d attempts: %s",
                        attempts_used, e,
                    )
                    break
                base = self.BACKOFF_SECONDS[
                    min(attempt, len(self.BACKOFF_SECONDS) - 1)
                ]
                # Spread of ±50% around the base: stays jittered enough that
                # two containers cannot lock-step onto the same wave, without
                # collapsing to a zero-length sleep the way full jitter can.
                delay = random.uniform(base * 0.5, base * 1.5)
                elapsed = time.monotonic() - started
                if elapsed + delay > self.RETRY_BUDGET_SECONDS:
                    logger.warning(
                        "Betway retry budget spent after %d attempt(s) in %.0fs: %s",
                        attempts_used, elapsed, e,
                    )
                    break
                logger.info(
                    "Betway fetch attempt %d/%d failed (retrying in %.1fs): %s",
                    attempts_used, self.MAX_ATTEMPTS, delay, e,
                )
                await asyncio.sleep(delay)
        return {"status": "error", "error": f"Max retries reached: {last_error}"}

    async def _fetch_event_safe(self, client, eid, reg_name, league, sem=None) -> Optional[Dict]:
        try:
            bw_headers = {
                "Referer": "https://www.betway.co.za/sport/horse-racing",
                "Origin": "https://www.betway.co.za",
            }
            if sem:
                async with sem:
                    await asyncio.sleep(random.uniform(0.2, 0.5))
            qs = f"eventIds={eid}&marketGroupName=&countryCode=ZA"
            data = await self._http_get("GetEvent", qs, bw_headers)
            if isinstance(data, dict):
                data["eventId"] = eid
                data["regionName"] = reg_name
                data["leagueName"] = league
                return data
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch event {eid}: {e}")
        return None

    def _count_priced(self, runners: list) -> int:
        return sum(1 for r in runners if isinstance(r.get("odds"), (int, float)) and r["odds"] > 0)

    async def get_snapshot_format(self) -> Dict[str, Any]:
        """Returns racing data in the flat 'market_snapshot' format used by the HUD and AlertEngine.

        ``fetch_ok`` distinguishes "the feed answered with an empty card"
        (dark day) from "the feed failed" (403/timeout). The cron's meeting
        gate needs that difference: an outage must never be cached as a dark
        day, or the monitor stands down and the card never comes back.
        """
        raw = await self.fetch_racing_data()
        if raw.get("status") == "error":
            return {"events": {}, "count": 0, "fetch_ok": False,
                    "fetch_error": str(raw.get("error", "unknown"))[:200]}

        events = {}
        for det in raw.get("details", []):
            try:
                eid = det.get("eventId")
                reg_name = det.get("regionName", "Unknown")
                league = det.get("leagueName", "Unknown")

                # GetEvent response: { result: { events: [...], outcomes: [...], prices: [...] } }
                res = det.get("result", det)
                event_obj = (res.get("events") or [{}])[0]

                # Skip finished races
                if event_obj.get("isFinished"):
                    continue

                # --- Race time from epoch on the event object ---
                race_time = "00:00"
                start_epoch = event_obj.get("expectedStartEpoch")
                if start_epoch:
                    try:
                        race_time = datetime.fromtimestamp(start_epoch).strftime("%H:%M")
                    except Exception:
                        pass

                # --- Race number from sportSpecificProperties ---
                race_num_prop = event_obj.get("sportSpecificProperties", {}).get("raceNumber")
                race_num = int(race_num_prop) if race_num_prop else 0
                if race_num == 0:
                    m = re.search(r"Race\s+(\d+)", event_obj.get("name", ""), re.IGNORECASE)
                    if m:
                        race_num = int(m.group(1))

                # --- Prices map: outcomeId (str) -> priceDecimal ---
                price_map = {
                    str(p["outcomeId"]): float(p.get("priceDecimal", 0))
                    for p in res.get("prices", [])
                    if isinstance(p, dict) and "outcomeId" in p
                }

                # --- Find the Win market ID (varies by region: "Race Winner", "To Win", "Win") ---
                _win_keywords = ("Race Winner", "Win Only", "To Win", "Winner", "Win")
                winner_market_id = next(
                    (str(mkt["marketId"]) for mkt in res.get("markets", [])
                     if any(k in mkt.get("name", "") for k in _win_keywords)),
                    None
                )
                name_price_map: dict = {}
                # outcomeIds flagged nonRunner — scratched horses keep a
                # roster slot (tagged below) instead of vanishing, so the
                # snapshot carries the NR signal to settlement (auto-VOID)
                # and the HUD (non-runner badge) instead of silent absence.
                non_runner_oids: set = set()
                for outcome in res.get("outcomes", []):
                    if winner_market_id and str(outcome.get("marketId")) != winner_market_id:
                        continue
                    if outcome.get("nonRunner"):
                        _oid = str(outcome.get("outcomeId") or "")
                        if _oid:
                            non_runner_oids.add(_oid)
                        continue
                    oid = str(outcome.get("outcomeId") or "")
                    price = price_map.get(oid)
                    if price:
                        name_key = (outcome.get("outcomeName") or outcome.get("name") or "").lower()
                        if name_key and name_key not in name_price_map:
                            name_price_map[name_key] = price

                # --- Build runners from raceEventDetails.racers (canonical source) ---
                # Fall back to outcomes filtered to Race Winner market if racers unavailable
                racers = (event_obj.get("raceEventDetails") or {}).get("racers") or []

                if racers:
                    runners = []
                    for r in racers:
                        outcome_id = str((r.get("outcomeIds") or [None])[0] or "")
                        odds = price_map.get(outcome_id)
                        if odds is None:
                            horse_name_key = (r.get("outcomeName") or r.get("name") or "").lower()
                            odds = name_price_map.get(horse_name_key, "SP")
                        runners.append({
                            "outcomeId": outcome_id,
                            "name": r.get("outcomeName") or r.get("name") or "Unknown",
                            "outcomeName": r.get("outcomeName") or r.get("name") or "Unknown",
                            "non_runner": outcome_id in non_runner_oids,
                            "jockeyName": r.get("jockeyName") or "TBA",
                            "trainerName": r.get("trainerName") or "TBA",
                            "age": r.get("age") or "U",
                            "weight": r.get("weight") or "0",
                            "form": r.get("form") or "",
                            "number": str(r.get("number") or "0"),
                            "draw": int(r.get("draw") or 0),
                            "timeForm": r.get("timeForm") or "",
                            "imageLocation": r.get("imageLocation") or "",
                            "starRating": int(r.get("starRating") or 0),
                            "odds": odds,
                        })
                else:
                    # Fallback: outcomes filtered to Race Winner market, skip non-runners
                    winner_market_id = next(
                        (str(mkt["marketId"]) for mkt in res.get("markets", [])
                         if "Race Winner" in mkt.get("name", "") or "Win Only" in mkt.get("name", "")),
                        None
                    )
                    seen = set()
                    runners = []
                    for outcome in res.get("outcomes", []):
                        if winner_market_id and str(outcome.get("marketId")) != winner_market_id:
                            continue
                        is_nr = bool(outcome.get("nonRunner"))
                        name = outcome.get("outcomeName") or outcome.get("name") or "Unknown"
                        if name in seen:
                            continue
                        seen.add(name)
                        outcome_id = str(outcome.get("outcomeId") or "")
                        info = outcome.get("additionalInfo") or {}
                        odds = price_map.get(outcome_id, "SP")
                        runners.append({
                            "outcomeId": outcome_id,
                            "name": name,
                            "outcomeName": name,
                            "non_runner": is_nr,
                            "jockeyName": info.get("JockeyName") or "TBA",
                            "trainerName": info.get("TrainerName") or "TBA",
                            "age": info.get("Age") or "U",
                            "weight": info.get("Weight") or "0",
                            "form": info.get("Form") or "",
                            "number": str(info.get("Number") or "0"),
                            "draw": int(info.get("Draw") or 0),
                            "timeForm": info.get("TimeForm") or "",
                            "imageLocation": info.get("ImageLocation") or "",
                            "starRating": int(info.get("StarRating") or 0),
                            "odds": odds,
                        })

                if not runners and det.get("price_source") != "daily":
                    continue

                priced = self._count_priced(runners)
                if priced < len(runners):
                    logger.info("Betway %s R%d: %d/%d runners have odds (rest SP)", league, race_num, priced, len(runners))

                name_text = event_obj.get("name") or event_obj.get("displayName") or ""

                events[str(eid)] = {
                    "id": eid,
                    "en": f"{reg_name}: {league}",
                    "course": league,
                    "name": name_text,
                    "t": race_time,
                    "st": race_time,
                    "raceNumber": race_num,
                    "isFinished": False,
                    "runners": runners,
                    # "daily" = field came from GetDaily, GetEvent was refused,
                    # so every runner is SP until a priced fetch lands.
                    "price_source": det.get("price_source") or "event",
                }
                if det.get("field_pending"):
                    events[str(eid)]["field_pending"] = True
            except Exception as e:
                logger.error(f"Error parsing event {det.get('eventId', '?')}: {e}")

        out = {"events": events, "count": len(events), "fetch_ok": True}
        if raw.get("daily_unpriced"):
            out["daily_unpriced"] = raw["daily_unpriced"]
        if raw.get("daily_ids"):
            out["daily_ids"] = raw["daily_ids"]
        if raw.get("daily_from_cache"):
            # Prices really were refreshed for the near-off races; the *card
            # list* came from the last good GetDaily, which is worth recording
            # in the feed-health log but is not a failed fetch.
            out["daily_from_cache"] = True
        # Durable last-good prices: a blocked GetEvent leaves whole meetings at
        # SP even though the race list arrived. Rehydrate only the races that
        # came back with no real price at all.
        try:
            out = _apply_price_cache(out)
        except Exception as exc:  # noqa: BLE001 - cache must never break a fetch
            logger.debug("Betway price cache skipped: %s", exc)
        return out

    async def get_races(self) -> List[ScrapedRace]:
        """Legacy compatibility wrapper for ScrapedRace objects."""
        snapshot = await self.get_snapshot_format()
        return self._parse_snapshot(snapshot)

    def _parse_snapshot(self, snapshot: Dict) -> List[ScrapedRace]:
        """Convert AdaptiveMonitor snapshot format (flat schema) to ScrapedRace objects."""
        scraped_races = []
        events = snapshot.get("events", {})

        for eid, e in events.items():
            try:
                track_raw = e.get("en", "Unknown")
                # Strip region prefix e.g. "South Africa: Turffontein" → "Turffontein"
                track = (
                    track_raw.split(":")[-1].strip() if ":" in track_raw else track_raw
                )
                runners = []
                for r in e.get("runners", []):
                    odds_val = r.get("odds", "SP")
                    try:
                        odds_decimal = float(odds_val) if odds_val != "SP" else 5.0
                    except (ValueError, TypeError):
                        odds_decimal = 5.0
                    runners.append(
                        ScrapedRunner(
                            horse_name=r.get("outcomeName") or r.get("name") or "Unknown",
                            odds_decimal=odds_decimal,
                            jockey=r.get("jockeyName") or "TBA",
                            trainer=r.get("trainerName") or "TBA",
                            barrier=int(r.get("draw") or 0),
                            form=r.get("form") or "",
                        )
                    )

                if runners:
                    scraped_races.append(
                        ScrapedRace(
                            track=track,
                            race_number=int(e.get("raceNumber", 1)),
                            race_time=e.get("t", "12:00"),
                            # Real distance from the snapshot (distance_m);
                            # None when absent — never a 1600m placeholder.
                            distance=_parse_distance_m(
                                e.get("distance_m"), e.get("name")
                            ),
                            track_condition="Good",
                            runners=runners,
                        )
                    )
            except Exception as ex:
                logger.debug(f"Error parsing snapshot event {eid}: {ex}")
                continue

        return scraped_races
