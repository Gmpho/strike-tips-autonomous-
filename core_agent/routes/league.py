"""Strike Tips predictor league — public board + pick submission.

Public reads (board, tipster profile, formula, today's races) are allowlisted
in core_agent.core.security.SAFE_PATHS. Pick submission requires a Supabase
user JWT (same auth model as /api/telegram/*).

v1 data source: data/bet_history.json (our own settled selections) expanded
into cohort rows (region / confidence tier / track). Picks submitted via
POST /api/league/picks are appended to data/league_picks.jsonl and folded
into the same board on the next read.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel

from core_agent.config.paths import DATA_DIR
from core_agent.skills.league.regions import region_of, region_label
from core_agent.skills.league.rollups import build_board
from core_agent.skills.league.scoring import (
    score_pick, base_points, sp_bonus, form_rating, value_index,
    MIN_TIPS_TO_QUALIFY, DECAY_DAYS,
)

router = APIRouter(prefix="/api/league", tags=["league"])

logger = logging.getLogger("league")

BET_HISTORY = os.path.join(str(DATA_DIR), "bet_history.json")
PICKS_LOG = os.path.join(str(DATA_DIR), "league_picks.jsonl")
PROFILES_LOG = os.path.join(str(DATA_DIR), "league_profiles.json")
LOCK_MINUTES = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_bets() -> List[Dict[str, Any]]:
    _sync_volume()
    if not os.path.exists(BET_HISTORY):
        return []
    try:
        with open(BET_HISTORY) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _expand_bets_to_picks(bets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Turn each settled bet into cohort pick dicts (region / tier / track).

    Paper bets are excluded from the public record.
    """
    out: List[Dict[str, Any]] = []
    for b in bets:
        if b.get("is_paper"):
            continue
        status = (b.get("status") or "").upper()
        # Only a real result counts. VOID/EXPIRED bets had no outcome (refunded
        # race, scratched runner, stale expiry) — including them as settled
        # losses deflated every regional strike rate on the analytics board.
        if status not in ("WON", "LOST"):
            continue
        won = status == "WON"
        track = b.get("track") or ""
        region = region_of(track)
        conf = b.get("confidence") or "AUTO"
        odds = float(b.get("odds") or 0)
        placed = b.get("placed")  # '1st'/'2nd'/... or None
        position = 1 if (placed == "1st" or won) else (
            2 if placed == "2nd" else (3 if placed == "3rd" else (4 if placed == "4th" else 99))
        )
        # Cohort 1: region
        out.append(_pick(b, "cohort", f"region:{region}", region_label(region) + " record",
                      region, won, odds, position, b))
        # Cohort 2: confidence tier
        out.append(_pick(b, "cohort", f"tier:{conf}", conf.replace("_", " ").title() + " tier",
                      region, won, odds, position, b))
        # Cohort 3: track
        out.append(_pick(b, "cohort", f"track:{track.lower()}", track.title() + " record",
                      region, won, odds, position, b))
    return out


def _pick(b, etype, eid, name, region, won, odds, position, raw) -> Dict[str, Any]:
    field_size = int(raw.get("field_size") or 8)
    sp = raw.get("winner_sp")
    pts = score_pick(field_size, position, odds, sp) if won else 0
    # For our own ledger we don't have field_size/SP; record 0 base + ROI proxy.
    # Form/value are recomputed from points + odds in rollups, so keep points
    # honest: a win contributes its odds as the value signal via winner_sp.
    if won and not sp:
        pts = int(round(odds))  # odds-as-points keeps form meaningful pre-SP
    return {
        "entity_type": etype,
        "entity_id": eid,
        "entity_name": name,
        "region": region,
        "date": raw.get("date"),
        "settled": True,
        "won": won,
        "points": pts,
        "winner_sp": float(sp) if sp else (float(odds) if won else 0.0),
        "pick_odds": odds,
    }


def _sync_volume() -> None:
    try:
        from core_agent.core.volume_sync import sync_volume
        sync_volume(max_age_secs=5)
    except Exception:
        pass


def _commit_volume() -> None:
    try:
        import os as _os
        if not _os.getenv("MODAL_TASK_ID"):
            return
        import modal
        vol = modal.Volume.from_name("strike-tips-data")
        vol.commit()
    except Exception:
        pass


def _load_user_picks() -> List[Dict[str, Any]]:
    _sync_volume()
    if not os.path.exists(PICKS_LOG):
        return []
    out = []
    try:
        with open(PICKS_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _user_from_token(authorization: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve (user_id, display_name, google_avatar_url) from a Supabase JWT.

    Returns (None, None, None) when the token is missing/invalid — callers must
    treat that as "not signed in" and never fall back to another identity.

    Raises 503 when the server itself is misconfigured (no Supabase URL/key):
    answering "sign in" there would send a correctly signed-in punter round in
    circles, which is exactly what happened inside Docker where .env only
    carries the VITE_SUPABASE_* aliases.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None, None, None
    token = authorization.split(None, 1)[1].strip()
    if not token:
        return None, None, None
    try:
        from core_agent.db.client import get_service_client
        client = get_service_client()
    except Exception as exc:
        logger.error("league auth backend unavailable: %s", exc)
        raise HTTPException(
            503,
            "Auth backend not configured on this server (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing)",
        )
    try:
        user_res = client.auth.get_user(token)
    except Exception as exc:
        logger.warning("league auth: token rejected: %s", exc)
        return None, None, None
    user = getattr(user_res, "user", None)
    if not user or not getattr(user, "id", None):
        return None, None, None
    meta = getattr(user, "user_metadata", None) or {}
    name = meta.get("full_name") or meta.get("name") or meta.get("preferred_username")
    avatar = meta.get("avatar_url") or meta.get("picture")
    return str(user.id), name, (str(avatar) if avatar else None)


# ── Avatar preferences ────────────────────────────────────────────────────
# Users choose how they appear. Google's photo is only a default: because the
# league board is public, we always let a player fall back to a preset or to
# plain initials instead of exposing their Google profile picture.
AVATAR_MODES = ("google", "preset", "initials")
AVATAR_PRESETS = [
    {"id": "jockey", "emoji": "🏇", "gradient": "from-amber-500 to-orange-600"},
    {"id": "trophy", "emoji": "🏆", "gradient": "from-yellow-400 to-amber-600"},
    {"id": "comet", "emoji": "☄️", "gradient": "from-indigo-500 to-purple-600"},
    {"id": "bolt", "emoji": "⚡", "gradient": "from-cyan-400 to-blue-600"},
    {"id": "fox", "emoji": "🦊", "gradient": "from-orange-400 to-rose-500"},
    {"id": "eagle", "emoji": "🦅", "gradient": "from-slate-500 to-slate-700"},
    {"id": "shark", "emoji": "🦈", "gradient": "from-teal-400 to-cyan-700"},
    {"id": "crown", "emoji": "👑", "gradient": "from-fuchsia-500 to-purple-700"},
]


def _load_profiles() -> Dict[str, Dict[str, Any]]:
    _sync_volume()
    if not os.path.exists(PROFILES_LOG):
        return {}
    try:
        with open(PROFILES_LOG) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_profiles(profiles: Dict[str, Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(PROFILES_LOG), exist_ok=True)
    tmp = PROFILES_LOG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(profiles, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, PROFILES_LOG)
    _commit_volume()


def _resolve_avatar(uid: str, google_url: Optional[str]) -> Dict[str, Any]:
    """Public-safe avatar descriptor for one player.

    Google's photo is the default (that is what the punter already uses), but
    the choice is theirs: the board is public, so `mode: preset` or
    `mode: initials` lets a player keep their face off it.
    """
    prof = _load_profiles().get(uid) or {}
    mode = prof.get("mode")
    preset_id = prof.get("preset")
    if mode not in AVATAR_MODES:
        mode = "google" if google_url else "initials"
    if mode == "google" and not google_url:
        mode = "initials"
    preset = next((p for p in AVATAR_PRESETS if p["id"] == preset_id), None)
    if mode == "preset" and not preset:
        mode = "initials"
    return {
        "mode": mode,
        "url": google_url if mode == "google" else None,
        "preset": preset["id"] if preset and mode == "preset" else None,
        "emoji": preset["emoji"] if preset and mode == "preset" else None,
        "gradient": preset["gradient"] if preset and mode == "preset" else None,
    }


@router.get("/board")
async def board(
    region: Optional[str] = Query(None),
    scope: str = Query("all"),  # all | region | tier | track
    sort: str = Query("form"),
    include_paper: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    _sync_volume()
    picks = _expand_bets_to_picks(_load_bets())
    picks += _load_user_picks()
    if region:
        picks = [p for p in picks if p.get("region") == region]
    if scope == "region":
        picks = [p for p in picks if str(p.get("entity_id", "")).startswith("region:")]
    elif scope == "tier":
        picks = [p for p in picks if str(p.get("entity_id", "")).startswith("tier:")]
    elif scope == "track":
        picks = [p for p in picks if str(p.get("entity_id", "")).startswith("track:")]
    rows = build_board(picks, _now_iso())
    # Only qualified + non-decayed by default for the ranked board.
    ranked = [r for r in rows if r.get("qualified") and not r.get("decayed")]
    # sort
    keymap = {
        "form": "form_rating", "value": "value_index",
        "strike": "strike_rate", "weekly": "weekly_points",
        "total": "total_points",
    }
    sk = keymap.get(sort, "form_rating")
    ranked.sort(key=lambda r: r.get(sk, 0), reverse=True)
    # re-rank after filter
    rk = 0
    prev = None
    for r in ranked:
        v = r.get(sk, 0)
        if v != prev:
            rk += 1
            prev = v
        r["rank"] = rk
    as_of = None
    try:
        as_of = datetime.fromtimestamp(os.path.getmtime(BET_HISTORY), tz=timezone.utc).isoformat()
    except Exception:
        pass
    return {
        "as_of": as_of,
        "now": _now_iso(),
        "min_tips": MIN_TIPS_TO_QUALIFY,
        "decay_days": DECAY_DAYS,
        "total_rows": len(rows),
        "ranked_rows": len(ranked),
        "rows": ranked[:limit],
        "all_rows": rows,
    }


@router.get("/tipster/{slug}")
async def tipster(slug: str):
    _sync_volume()
    picks = _expand_bets_to_picks(_load_bets()) + _load_user_picks()
    rows = build_board(picks, _now_iso())
    row = next((r for r in rows if r.get("entity_id") == slug), None)
    if not row:
        # try handle match
        row = next((r for r in rows if r.get("handle") == slug), None)
    if not row:
        raise HTTPException(404, "not found")
    # gather raw picks for this entity
    raw = [p for p in picks if p.get("entity_id") == (row.get("entity_id"))]
    # `won` means "scored" (top 3). Wins are firsts only, so derive from the
    # recorded finishing position and fall back to the flag for legacy rows.
    wins = [p for p in raw if _is_win(p)]
    places = [p for p in raw if _is_place(p)]
    # finish distribution
    dist = {"1st": 0, "2nd": 0, "3rd": 0, "4th": 0, "unplaced": 0}
    for p in raw:
        if p.get("void"):
            continue
        fp = p.get("finish_position")
        if fp == 1:
            dist["1st"] += 1
        elif fp == 2:
            dist["2nd"] += 1
        elif fp == 3:
            dist["3rd"] += 1
        elif fp == 4:
            dist["4th"] += 1
        else:
            dist["unplaced"] += 1
    # recent form last 100
    recent = sorted(raw, key=lambda p: str(p.get("date") or ""), reverse=True)[:100]
    recent_wins = sum(1 for p in recent if _is_win(p))
    # favourite tracks (count by course)
    track_counts: Dict[str, int] = {}
    for p in raw:
        c = str(p.get("course") or "").strip()
        if c:
            track_counts[c] = track_counts.get(c, 0) + 1
    favourite_tracks = sorted(track_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]

    # recent picks (newest first) so the UI can show "what horses they played"
    recent_picks = sorted(raw, key=lambda p: str(p.get("date") or ""), reverse=True)[:50]
    pick_rows = [
        {
            "date": p.get("date"),
            "course": p.get("course"),
            "race_number": p.get("race_number"),
            "runner_number": p.get("runner_number"),
            "runner_name": p.get("runner_name"),
            "pick_odds": p.get("pick_odds"),
            "settled": bool(p.get("settled")),
            "won": bool(p.get("won")),
            "void": bool(p.get("void")),
            "void_reason": p.get("void_reason"),
            "placed": bool(p.get("placed")),
            "finish_position": p.get("finish_position"),
            "points": p.get("points", 0),
        }
        for p in recent_picks
    ]

    settled_raw = [p for p in raw if p.get("settled")]
    return {
        "profile": row,
        "tips": len(raw),
        "settled": len(settled_raw),
        "wins": len(wins),
        "places": len(places),
        "distribution": dist,
        "recent_form": {
            "n": len(recent),
            "wins": recent_wins,
            "strike_rate": (recent_wins / len(recent)) if recent else 0.0,
        },
        "best_streak": _best_streak(raw),
        "avg_odds_winners": (sum(p.get("winner_sp", 0) for p in wins) / len(wins)) if wins else 0.0,
        "favourite_tracks": [{"track": t, "count": c} for t, c in favourite_tracks],
        "picks": pick_rows,
    }


def _is_win(p: Dict[str, Any]) -> bool:
    """True when the pick crossed the line first.

    `won` is the settlement flag for "scored" (top 4). Legacy rows carry no
    finishing position, so fall back to the flag for them only.
    """
    pos = p.get("finish_position")
    return pos == 1 or (pos is None and bool(p.get("won")))


def _is_place(p: Dict[str, Any]) -> bool:
    """True for any scoring finish (1st-4th)."""
    pos = p.get("finish_position")
    return pos in (1, 2, 3, 4) or (pos is None and bool(p.get("won")))


def _best_streak(picks: List[Dict[str, Any]]) -> int:
    best = cur = 0
    for p in sorted(picks, key=lambda x: str(x.get("date") or "")):
        if _is_win(p):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


@router.get("/formula")
async def formula():
    """Published scoring formula + worked examples (served from the engine)."""
    ex1 = {
        "scenario": "Winner of a 12-runner race at SP 5.0",
        "field_size": 12, "position": 1, "taken_odds": 4.5, "winner_sp": 5.0,
        "points": score_pick(12, 1, 4.5, 5.0),
        "base_points": base_points(12),
        "sp_bonus": sp_bonus(5.0),
    }
    ex2 = {
        "scenario": "Winner of an 8-runner race at SP 2.0 (short price)",
        "field_size": 8, "position": 1, "taken_odds": 1.9, "winner_sp": 2.0,
        "points": score_pick(8, 1, 1.9, 2.0),
        "base_points": base_points(8),
        "sp_bonus": sp_bonus(2.0),
    }
    ex3 = {
        "scenario": "Unplaced pick in a 10-runner race",
        "field_size": 10, "position": 5, "taken_odds": 6.0, "winner_sp": 3.0,
        "points": score_pick(10, 5, 6.0, 3.0),
    }
    ex4 = {
        "scenario": "4th place in a 12-runner race",
        "field_size": 12, "position": 4, "taken_odds": 7.0, "winner_sp": 4.0,
        "points": score_pick(12, 4, 7.0, 4.0),
        "base_points": base_points(12),
    }
    return {
        "min_tips_to_qualify": MIN_TIPS_TO_QUALIFY,
        "decay_days": DECAY_DAYS,
        "form_scale": "50 = site average, 100 = double the site average",
        "value_scale": "100 = site average winner starting price",
        "rules": [
            "One pick per race per player. A second submission is rejected.",
            "Picks lock 5 minutes before the off (enforced in the database).",
            "A pick scores when the horse finishes in the top 4 (1st/2nd/3rd/4th).",
            "1st = field size + starting-price bonus; 2nd = half the field; 3rd = a quarter; 4th = an eighth.",
            "Starting-price bonus = min(40, round(6 * (SP - 1))), winners only.",
            "Finishing 5th or worse scores zero but still counts as a settled tip.",
            "Form rating = 50 * (your avg points per tip / site avg points per tip), clamped 0-100.",
            "Value index = 100 * (your avg winner SP / site avg winner SP).",
            "Strike rate = wins / settled tips.",
            "Fewer than 5 settled tips in 30 days: not ranked.",
            "No settled tip in 7 days: decays off the board.",
            "Points only - never money, stakes or bankroll state.",
        ],
        "worked_examples": [ex1, ex2, ex3, ex4],
    }


class PickIn(BaseModel):
    race_id: str
    course: Optional[str] = None
    race_number: Optional[int] = None
    # Off time is resolved server-side when the client cannot supply it.
    # Betfair's date stamp on a race is intermittent, so the HUD sometimes
    # received off_iso=null and every pick died on "Input should be a valid
    # string" (Nov-2026) — the race was fine, the field was empty.
    off_iso: Optional[str] = None
    runner_number: int
    runner_name: Optional[str] = None
    odds: float = 0.0
    region: Optional[str] = None
    # Field size at pick time. Settlement scores a win by field size, and the
    # market snapshot for yesterday's races is gone by the time we settle.
    field_size: Optional[int] = None


def _snapshot_sast_day(snap: Dict[str, Any]) -> Optional[str]:
    """The calendar day (SAST) the snapshot was written on.

    ``timestamp`` is stamped in UTC by the snapshot writer; SA runs two hours
    ahead, so a card written late at night still belongs to the next SA day.
    """
    raw = str((snap or {}).get("timestamp") or "")[:19]
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return raw[:10] or None
    return (stamp + timedelta(hours=2)).date().isoformat()


def _race_event(snap: Dict[str, Any], race_id: str) -> Optional[Dict[str, Any]]:
    """Find a race's event in the market snapshot by id."""
    events = (snap or {}).get("events") or {}
    if not isinstance(events, dict):
        events = {}
    ev = events.get(str(race_id))
    if isinstance(ev, dict):
        return ev
    for candidate in events.values():
        if isinstance(candidate, dict) and str(candidate.get("id")) == str(race_id):
            return candidate
    return None


def _snapshot_off_iso(snap: Dict[str, Any], race_id: str) -> Optional[str]:
    """Rebuild a race's off time from the market snapshot.

    Betfair stamps ``bf_event_date``/``bf_off_time`` on the events it
    matched, but that merge is intermittent: when it is missing the card
    still carries the race clock, and the snapshot's own day completes the
    timestamp. Without this a perfectly good card looked "no off time" and
    no pick could be submitted against it.
    """
    ev = _race_event(snap, race_id)
    if not isinstance(ev, dict):
        return None
    bf_date = str(ev.get("bf_event_date") or "")[:10]
    bf_time = str(ev.get("bf_off_time") or "")
    if bf_date and bf_time:
        return f"{bf_date}T{bf_time}:00+02:00"
    day = _snapshot_sast_day(snap)
    clock = str(ev.get("t") or ev.get("st") or "")
    if day and len(clock) >= 4 and clock[2] == ":":
        return f"{day}T{clock}:00+02:00"
    return None


def _load_snapshot() -> Dict[str, Any]:
    """The market snapshot as written by the odds monitor."""
    path = os.path.join(str(DATA_DIR), "market_snapshot_latest.json")
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@router.post("/picks")
async def submit_pick(body: PickIn, authorization: Optional[str] = Header(None)):
    uid, handle, google_avatar = _user_from_token(authorization)
    if not uid:
        raise HTTPException(401, "Sign in to pick")
    handle = handle or (uid[:8] if uid else "player")
    if not body.runner_name:
        raise HTTPException(422, "That runner has no name — pick another")
    # Off time: trust the client's, but fall back to the snapshot when the
    # client had none (an intermittent Betfair date stamp, not a bad pick).
    off_iso = body.off_iso
    if not off_iso:
        try:
            off_iso = _snapshot_off_iso(_load_snapshot(), body.race_id)
        except Exception:
            off_iso = None
    if not off_iso:
        raise HTTPException(
            422, "No off time for this race yet — try again in a minute"
        )
    # lock check
    try:
        off = datetime.fromisoformat(off_iso.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, "bad off_iso")
    if datetime.now(timezone.utc) >= off - timedelta(minutes=LOCK_MINUTES):
        raise HTTPException(409, "locked")
    # duplicate check (log scan)
    for p in _load_user_picks():
        if p.get("user_id") == uid and p.get("race_id") == body.race_id:
            raise HTTPException(409, "already-picked")
    course = body.course or ""
    region = body.region or region_of(course)
    row = {
        "entity_type": "player",
        "entity_id": uid,
        "entity_name": handle,
        "handle": handle,
        "region": region,
        "date": off.date().isoformat(),
        "settled": False,
        "won": False,
        "points": 0,
        "winner_sp": 0.0,
        "pick_odds": float(body.odds or 0),
        "user_id": uid,
        "race_id": body.race_id,
        "course": course,
        "race_number": body.race_number,
        "off_iso": off_iso,
        "runner_number": body.runner_number,
        "runner_name": body.runner_name,
        "field_size": body.field_size,
        "created_at": _now_iso(),
        "dedup_key": f"{body.race_id}|{uid}",
        "avatar": _resolve_avatar(uid, google_avatar),
    }
    os.makedirs(os.path.dirname(PICKS_LOG), exist_ok=True)
    with open(PICKS_LOG, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())
    _commit_volume()
    return {"ok": True, "locked_at": (off - timedelta(minutes=LOCK_MINUTES)).isoformat()}


@router.get("/races")
async def races(date: Optional[str] = Query(None), region: Optional[str] = Query(None)):
    _sync_volume()
    snap_path = os.path.join(str(DATA_DIR), "market_snapshot_latest.json")
    if not os.path.exists(snap_path):
        return {"races": [], "as_of": None}
    try:
        with open(snap_path) as f:
            snap = json.load(f)
    except Exception:
        return {"races": [], "as_of": None}
    events = snap.get("events", {})
    if isinstance(events, dict):
        events = list(events.values())
    # crowd counts per race from submitted picks
    user_picks = _load_user_picks()
    # One profile read for the whole payload: a player's CURRENT avatar
    # choice must win over whatever was stored on an older pick, otherwise
    # switching away from a Google photo would leave it on old rows.
    profiles = _load_profiles()
    crowd_by_race: dict = {}
    backers_by_race: dict = {}
    for p in user_picks:
        rid = p.get("race_id")
        rn = p.get("runner_number")
        if rid is None or rn is None:
            continue
        crowd_by_race.setdefault(rid, {})
        crowd_by_race[rid][rn] = crowd_by_race[rid].get(rn, 0) + 1
        # Who backed what, so the UI can show a tipmeerkat-style "what others
        # picked" strip with avatars. Picks are public and attributed.
        stored = p.get("avatar") or {}
        uid = p.get("user_id")
        avatar = (_resolve_avatar(uid, stored.get("url")) if uid in profiles else stored) or None
        backers_by_race.setdefault(rid, []).append({
            "handle": p.get("entity_name") or p.get("handle"),
            "user_id": uid,
            "avatar": avatar,
            "runner_number": rn,
            "runner_name": p.get("runner_name"),
        })

    out = []
    snap_day = _snapshot_sast_day(snap)
    for e in events or []:
        course = e.get("course") or ""
        r = region_of(course)
        if region and r != region:
            continue
        runners = [x for x in (e.get("runners") or []) if not x.get("non_runner")]
        off = e.get("bf_off_time") or e.get("t")
        rid = str(e.get("id"))
        off_iso = None
        if e.get("bf_event_date") and e.get("bf_off_time"):
            off_iso = f"{e['bf_event_date']}T{e['bf_off_time']}:00+02:00"
        elif snap_day:
            # Betfair's date stamp is intermittent; the card's own clock plus
            # the snapshot's day is enough. Without this the HUD got
            # off_iso=null and no pick could be submitted (Nov-2026).
            clock = str(e.get("t") or e.get("st") or "")
            if len(clock) >= 4 and clock[2] == ":":
                off_iso = f"{snap_day}T{clock}:00+02:00"
        out.append({
            "race_id": rid,
            "course": course,
            "region": r,
            "race_number": e.get("raceNumber"),
            "off": off,
            "off_iso": off_iso,
            "distance_m": e.get("distance_m"),
            "field_size": len(runners),
            "runners": [
                {
                    "number": x.get("number"),
                    "name": x.get("name"),
                    "odds": x.get("odds"),
                    "jockey": x.get("jockeyName"),
                    "trainer": x.get("trainerName"),
                    "pedigree": x.get("pedigree"),
                    "age": x.get("age"),
                    "weight": x.get("weight"),
                    "draw": x.get("draw"),
                    "form": x.get("form"),
                    "days_since_run": x.get("daysSinceRun"),
                    "rating": x.get("official_rating"),
                    "claim": x.get("jockey_claim"),
                    "star": x.get("starRating"),
                }
                for x in runners
            ],
            "is_finished": bool(e.get("isFinished")),
            "crowd": crowd_by_race.get(rid, {}),
            "backers": backers_by_race.get(rid, []),
            "ai_selections": e.get("aiSelections"),
        })
    return {"as_of": snap.get("timestamp"), "races": out}


@router.get("/me")
async def me(response: Response, authorization: Optional[str] = Header(None)):
    """Everything the signed-in punter needs: profile, summary and FULL pick
    history (not just today) so yesterday's picks are never invisible.

    Scoped strictly to the token's user id — the response is never cached by
    a shared cache (private, no-store) because it is per-account data.
    """
    uid, handle, google_avatar = _user_from_token(authorization)
    if not uid:
        raise HTTPException(401, "sign in")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    _sync_volume()
    picks = [p for p in _load_user_picks() if p.get("user_id") == uid]
    picks.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)
    settled = [p for p in picks if p.get("settled")]
    wins = sum(1 for p in settled if _is_win(p))
    places = sum(1 for p in settled if _is_place(p))
    points = sum(int(p.get("points") or 0) for p in settled)
    return {
        "user_id": uid,
        "handle": handle or uid[:8],
        "avatar": _resolve_avatar(uid, google_avatar),
        "has_google_avatar": bool(google_avatar),
        # The punter's own Google photo, so the avatar picker can preview it.
        # Only ever returned on this private, per-account response.
        "google_avatar_url": google_avatar,
        "avatar_presets": AVATAR_PRESETS,
        "picks": picks,
        "summary": {
            "tips": len(picks),
            "settled": len(settled),
            "pending": len(picks) - len(settled),
            "wins": wins,
            "places": places,
            "strike_rate": (wins / len(settled)) if settled else 0.0,
            "place_rate": (places / len(settled)) if settled else 0.0,
            "points": points,
            "qualified": len(settled) >= MIN_TIPS_TO_QUALIFY,
            "needed": max(0, MIN_TIPS_TO_QUALIFY - len(settled)),
        },
    }


class AvatarIn(BaseModel):
    mode: str  # google | preset | initials
    preset: Optional[str] = None


@router.post("/me/avatar")
async def set_avatar(body: AvatarIn, authorization: Optional[str] = Header(None)):
    """Choose how you appear on the public board.

    The league board is public, so a player can drop their Google photo and
    show a preset avatar or plain initials instead.
    """
    uid, _handle, google_avatar = _user_from_token(authorization)
    if not uid:
        raise HTTPException(401, "sign in")
    mode = (body.mode or "").strip().lower()
    if mode not in AVATAR_MODES:
        raise HTTPException(400, f"mode must be one of {', '.join(AVATAR_MODES)}")
    preset = (body.preset or "").strip() or None
    if mode == "preset" and preset not in {p["id"] for p in AVATAR_PRESETS}:
        raise HTTPException(400, "unknown preset")
    if mode == "google" and not google_avatar:
        raise HTTPException(400, "your account has no Google photo — pick a preset or initials")
    profiles = _load_profiles()
    profiles[uid] = {"mode": mode, "preset": preset if mode == "preset" else None}
    _save_profiles(profiles)
    return {"ok": True, "avatar": _resolve_avatar(uid, google_avatar), "has_google_avatar": bool(google_avatar)}


class ResultRunnerIn(BaseModel):
    name: str
    position: Optional[int] = None
    number: Optional[int] = None
    odds_decimal: Optional[float] = None


class RaceResultIn(BaseModel):
    date: str
    course: str
    race_number: Any
    runners: List[ResultRunnerIn]
    source: Optional[str] = "operator"


class IngestResultsIn(BaseModel):
    races: List[RaceResultIn]


@router.post("/ingest-results")
async def ingest_results(body: IngestResultsIn):
    """Operator / admin ingestion of confirmed race results into confirmed_results.jsonl.

    Accepts official cards (finishing positions 1st-4th + SP odds). Idempotently
    writes/updates confirmed_results.jsonl and triggers settlement of any open picks.
    Protected by API key via auth_middleware.
    """
    from core_agent.skills.league.results_feed import append_confirmed_results
    from core_agent.skills.league.settlement import settle_open_picks

    races = []
    for r in body.races:
        runners = []
        for runner in r.runners:
            runners.append({
                "number": runner.number or 0,
                "name": str(runner.name).strip(),
                "position": runner.position,
                "odds_decimal": float(runner.odds_decimal) if runner.odds_decimal else None,
            })
        races.append({
            "date": str(r.date)[:10],
            "course": str(r.course).strip(),
            "race_number": str(r.race_number).strip(),
            "runners": runners,
            "source": r.source or "operator",
        })

    written = append_confirmed_results(str(DATA_DIR), races)
    settle_stats = settle_open_picks(str(DATA_DIR))
    _commit_volume()
    return {
        "ok": True,
        "races_ingested": written,
        "settlement": settle_stats,
    }
