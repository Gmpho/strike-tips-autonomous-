import logging
import asyncio
import json
import os
import re
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from .tab4racing import ScrapedRace, ScrapedRunner, _parse_distance_m
from core_agent.core.http_client import get_async_client

logger = logging.getLogger("betway-api")

# One-shot diagnostic: log Betway's own region labels the first time we
# fetch, so the ALLOWED whitelist can be confirmed from production data
# rather than guessed (see the Gulf comment in fetch_racing_data).
_REGION_LABELS_LOGGED = False

# Per-event refresh bookkeeping (Nov-21). Betway's Cloudflare scoring tightens
# as request volume rises, and a 92-race international card re-fetched every
# five minutes is ~1,100 GetEvent calls/hour from one datacenter IP — for races
# that jump hours later. The budget keeps near-off races fresh every cycle and
# lets far-off ones ride, cutting volume ~80% without starving any race.
_REFRESH_STATE_PATH = os.environ.get("BETWAY_REFRESH_STATE") or str(
    Path(__file__).resolve().parents[3] / "data" / "betway_refresh_state.json"
)
_REFRESH_CACHE: Dict[str, float] = {}


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

    async def _http_get(self, path: str, qs: str, headers: dict) -> Optional[Dict[str, Any]]:
        """Fetch a Betway TrackRacing endpoint, falling back to the Worker proxy.

        Returns parsed JSON on success, None on failure (so callers can retry).
        """
        # 1. Try direct fetch (curl_cffi with fresh session and browser fingerprint)
        try:
            client = get_async_client(timeout=90.0, no_proxy=True,
                                     resolve_hosts={"www.betway.co.za"})
            url = f"{self.BASE_URL}/{path}?{qs}"
            resp = await client.get(url, headers=headers)
            status = getattr(resp, "status_code", None)
            if status == 200 or status is None:
                if hasattr(resp, "raise_for_status"):
                    resp.raise_for_status()
                return resp.json()
            if status != 200:
                logger.debug("Betway direct fetch HTTP %s on %s — attempting Worker proxy", status, path)
        except Exception as e:
            logger.debug("Betway direct fetch failed on %s: %s — attempting Worker proxy", path, e)

        # 2. Worker proxy fallback (Cloudflare edge IPs bypass datacenter IP blocks)
        url, key = self._worker_config()
        if key:
            try:
                import httpx
                worker_headers = {
                    "x-api-key": key,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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
                logger.warning("Worker proxy %s returned %d: %.120s", path, resp.status_code, resp.text)
            except Exception as e:
                logger.debug("Worker proxy failed on %s: %s", path, e)

        return None

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
        started = time.monotonic()
        last_error: Optional[BaseException] = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                client = get_async_client(
                    timeout=90.0,
                    no_proxy=True,
                    resolve_hosts={"www.betway.co.za"},
                )
                daily_qs = "sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2"
                data = await self._http_get("GetDaily", daily_qs, bw_headers)
                if data is None:
                    raise RuntimeError("Betway GetDaily returned no data (direct + proxy both failed)")

                event_ids = []
                ALLOWED = [
                    "South Africa",
                    "UK and Ireland",
                    "Australia",
                    "New Zealand",
                    "USA",
                    "Hong Kong",
                    "Japan",
                    "France",
                    # Gulf (Nov-2026): the UAE season runs Oct-Apr (Abu Dhabi
                    # from 22 Oct, Meydan's Carnival from 6 Nov) and Bahrain
                    # races through the winter. Without these the region filter
                    # dropped both before an event id was ever fetched, so the
                    # Gulf could never reach the snapshot however the course
                    # map looked. Names are substring-matched and only the
                    # venues we can settle are listed.
                    "United Arab Emirates",
                    "UAE",
                    "Bahrain",
                ]

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
                tasks = [
                    self._fetch_event_safe(client, eid, reg_name, league, sem)
                    for eid, reg_name, league, _ in to_fetch
                ]

                events_details = await asyncio.gather(*tasks)
                events_details = [e for e in events_details if e]

                # Remember what actually answered, so a failed event is retried
                # next cycle instead of being parked for FAR_REFRESH_SECONDS.
                for detail in events_details:
                    fetched_id = detail.get("eventId")
                    if fetched_id is not None:
                        budget_state[str(fetched_id)] = now_epoch
                if full_sweep:
                    budget_state["_last_sweep"] = now_epoch
                _save_refresh_state(budget_state, now_epoch)

                # GetDaily answered with events but every per-event call failed:
                # a bot-blocked wave, not a dark day. Return an error so the HUD
                # says the feed is broken instead of showing an empty card.
                if to_fetch and not events_details:
                    raise RuntimeError(
                        f"Betway GetDaily returned {len(to_fetch)} events but "
                        "all per-event GetEvent calls failed"
                    )

                return {"status": "success", "details": events_details}
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

                if not runners:
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
                }
            except Exception as e:
                logger.error(f"Error parsing event {det.get('eventId', '?')}: {e}")

        return {"events": events, "count": len(events), "fetch_ok": True}

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
