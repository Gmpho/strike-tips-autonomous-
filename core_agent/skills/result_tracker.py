"""
Result Tracker - Auto-settle open bets using search service (DDGS + direct SA scraper).
Uses fuzzy matching on horse names with date fallback (today → yesterday → no date).
"""

import logging
import re
from datetime import date, datetime, timedelta, timezone
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

    def _fuzzy_match(self, name_a: str, name_b: str) -> float:
        a = set(name_a.lower().split())
        b = set(name_b.lower().split())
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        return intersection / max(len(a), len(b))

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
        # ATR only serves today/yesterday result pages, so a ticket older
        # than 1 day can NEVER be verified against its own race day —
        # settling it would score it against a different day's winners.
        try:
            if (_bet_age_days(getattr(bet, "date", None)) or 0) > 1:
                return None
        except Exception:
            pass
        ticket = _parse_exotic_ticket(bet)
        if not ticket or not ticket["combos"]:
            return None
        requirement = _exotic_requirement(ticket["pool_type"])
        legs = ticket["pool_legs"]

        try:
            from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
            atr = AtTheRacesAPI()
            races = await atr.get_results_for_track(
                getattr(bet, "track", ""), date=atr_date_label(getattr(bet, "date", None))
            )
        except Exception as e:
            logger.debug(f"Exotic ATR lookup failed for {bet.bet_id}: {e}")
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
                logger.info(
                    "Exotic %s all legs placed, awaiting tote dividend — left PENDING",
                    bet.bet_id,
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
            if brain and brain.strike and brain.strike.telegram:
                await brain.strike.telegram.send_bet_result(
                    horse=bet.horse,
                    track=getattr(bet, "track", ""),
                    race_number=getattr(bet, "race_number", 0),
                    won=won,
                    stake=getattr(bet, "stake", 0.0),
                    returns=pool_return if won else 0.0,
                    profit_loss=(pool_return - float(getattr(bet, "stake", 0.0))) if won else -float(getattr(bet, "stake", 0.0)),
                )
        except Exception as tg_err:
            logger.warning(f"Failed to dispatch Telegram exotic result: {tg_err}")
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

        open_bets = gov.get_open_bets()
        if not open_bets:
            return []

        settled = []
        deferred: List[str] = []
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
            result_text = await self._search_result(bet.track, bet.race_number, bet_date=bet.date)
            if not result_text:
                continue

            # 1. Direct check if our horse is declared winner
            winner, confidence = self._extract_winner(result_text, [bet.horse])
            settle_needed = False
            won = False
            notes = ""

            if winner and confidence >= 0.55:
                won = True
                settle_needed = True
                notes = f"Auto-settled (WINNER confirmed, confidence={confidence:.0%})"
            else:
                # 2. Check if a DIFFERENT winner was confirmed for this race
                confirmed_winner = self._extract_race_winner(result_text)
                if confirmed_winner:
                    match_score = self._fuzzy_match(confirmed_winner, bet.horse)
                    if match_score >= 0.55:
                        won = True
                        settle_needed = True
                        notes = f"Auto-settled (WINNER: {confirmed_winner}, confidence={match_score:.0%})"
                    else:
                        won = False
                        settle_needed = True
                        notes = f"Auto-settled (LOST - 1st was {confirmed_winner})"

            if settle_needed:
                settled_ok = False
                try:
                    if brain and brain.strike:
                        # settle_bet returns a status dict (never raises on a
                        # failed settle) — honor its "settled" flag instead of
                        # assuming success, or we log/notify phantom settles.
                        _res = brain.strike.settle_bet(bet.bet_id, won=won, notes=notes)
                        settled_ok = bool(_res.get("settled")) if isinstance(_res, dict) else bool(_res)
                except Exception as brain_err:
                    logger.debug(f"Brain settle fallback to governor: {brain_err}")

                if not settled_ok and gov:
                    settled_ok = gov.settle_bet(bet.bet_id, won=won, notes=notes)

                if settled_ok:
                    logger.info(
                        f"Auto-settled: {bet.horse} at {bet.track} R{bet.race_number} - {'WON' if won else 'LOST'} ({notes})"
                    )
                    profit_loss = (bet.actual_return or 0.0) - bet.stake if won else -bet.stake
                    try:
                        if brain and brain.strike and brain.strike.telegram:
                            await brain.strike.telegram.send_bet_result(
                                horse=bet.horse,
                                track=bet.track,
                                race_number=bet.race_number,
                                won=won,
                                stake=bet.stake,
                                returns=bet.actual_return or 0.0,
                                profit_loss=profit_loss,
                            )
                    except Exception as tg_err:
                        logger.warning(f"Failed to dispatch Telegram result alert: {tg_err}")

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
        return settled
