"""Build a leaderboard board from a list of settled-pick dicts.

A pick dict has keys:
  entity_type  ('player' | 'cohort')
  entity_id    (user id or cohort slug)
  entity_name  (display handle)
  region       (region code)
  date         (ISO date 'YYYY-MM-DD' or datetime)
  won          (bool)
  points       (int)
  winner_sp    (float, SP of the winner of that race, 0 if unknown)
  pick_odds    (float, odds the pick was taken at)
  settled      (bool)   -- False => pending, excluded from settled counts
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .scoring import (
    form_rating, value_index, strike_rate, qualifies, decayed,
    MIN_TIPS_TO_QUALIFY, DECAY_DAYS,
)

WEEK_START_SAST_OFFSET_HOURS = 2  # Monday 00:00 SAST == Sunday 22:00 UTC


def _iso_date(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    s = str(v)
    return s[:10]


def _parse_date(v: Any) -> datetime:
    s = _iso_date(v)
    try:
        return datetime.fromisoformat(s + "T00:00:00+00:00")
    except Exception:
        return datetime.now(timezone.utc)


def _monday_of(dt: datetime) -> datetime:
    # Monday 00:00 UTC-ish; we approximate with the SAST Monday.
    d = dt - timedelta(days=dt.weekday())
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def build_board(picks: List[Dict[str, Any]], now_iso: str) -> List[Dict[str, Any]]:
    """Aggregate picks into ranked board rows.

    Returns rows sorted by form desc, with tie-breaks by value then total.
    Qualification + decay are flagged but rows are still returned (the caller
    decides whether to filter).
    """
    groups: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {
        "settled": 0, "pending": 0, "wins": 0, "places": 0, "points": 0,
        "winner_sp_sum": 0.0, "winner_sp_n": 0,
        "pick_odds_sum": 0.0, "pick_odds_n": 0,
        "weekly_points": 0,
        "last_settled": None,
        "name": "", "name_at": "", "region": "", "region_counts": {},
        "avatar": None,
    })

    now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    week_start = _monday_of(now_dt)

    for p in picks:
        etype = p.get("entity_type", "player")
        eid = p.get("entity_id")
        region = p.get("region") or "OTHER"
        # A punter is one entity across every region they play; only cohorts
        # are region-scoped. Keying players by region split the same account
        # into several rows (SA picks vs UK picks showed up as two punters).
        key = (etype, eid) if etype == "player" else (etype, eid, region)
        g = groups[key]
        created = str(p.get("created_at") or p.get("date") or "")
        if p.get("entity_name") and created >= g["name_at"]:
            g["name"] = p["entity_name"]
            g["name_at"] = created
        g["region_counts"][region] = g["region_counts"].get(region, 0) + 1
        g["region"] = max(g["region_counts"].items(), key=lambda kv: kv[1])[0]
        # Newest pick carries the player's current avatar choice; older rows
        # written before avatars existed simply leave it as None.
        if p.get("avatar"):
            g["avatar"] = p["avatar"]
        # Pending tips never score, but the punter still exists: counting them
        # keeps a tipster who has only open picks on the community list.
        if not p.get("settled", True):
            g["pending"] += 1
            continue
        g["settled"] += 1
        won = bool(p.get("won"))
        pos = p.get("finish_position")
        # wins == crossed the line first. `won` is the settlement flag for
        # "scored" (top 4), so counting it as a win read as "70% strike rate"
        # on one actual winner (2026-11-06). Legacy rows carry no position, so
        # fall back to the flag for them only.
        is_win = pos == 1 or (pos is None and won)
        is_place = pos in (1, 2, 3, 4) or (pos is None and won)
        if is_win:
            g["wins"] += 1
        if is_place:
            g["places"] += 1
        pts = int(p.get("points") or 0)
        g["points"] += pts
        sp = p.get("winner_sp")
        if sp and float(sp) > 0:
            g["winner_sp_sum"] += float(sp)
            g["winner_sp_n"] += 1
        po = p.get("pick_odds")
        if po and float(po) > 0:
            g["pick_odds_sum"] += float(po)
            g["pick_odds_n"] += 1
        d = _parse_date(p.get("date"))
        if d >= week_start:
            g["weekly_points"] += pts
        if g["last_settled"] is None or d > g["last_settled"]:
            g["last_settled"] = d

    # Site-wide baselines for normalisation.
    total_settled = sum(g["settled"] for g in groups.values())
    site_avg_points = (sum(g["points"] for g in groups.values()) / total_settled) if total_settled else 0.0
    site_winner_sp_n = sum(g["winner_sp_n"] for g in groups.values())
    site_avg_winner_sp = (sum(g["winner_sp_sum"] for g in groups.values()) / site_winner_sp_n) if site_winner_sp_n else 0.0

    # Punters are compared with punters, not with the cohort aggregates. The
    # cohort rows carry ~2,400 settled entries at ~0.7 pts/tip, which dragged
    # the site average so low that every real player pinned at the 100 cap —
    # a 30-pt/4-tip record and a 21-pt/5-tip record both read "100.0".
    player_settled = sum(g["settled"] for k, g in groups.items() if k[0] == "player")
    player_points = sum(g["points"] for k, g in groups.items() if k[0] == "player")
    # Only trust the player baseline once there is a real sample; below that
    # the whole-site average is the calmer comparison.
    player_avg_points = (
        (player_points / player_settled)
        if player_settled >= 10 else site_avg_points
    )

    rows = []
    for key, g in groups.items():
        etype, eid = key[0], key[1]
        region = g["region"] or (key[2] if len(key) > 2 else "OTHER")
        avg_pts = (g["points"] / g["settled"]) if g["settled"] else 0.0
        avg_winner_sp = (g["winner_sp_sum"] / g["winner_sp_n"]) if g["winner_sp_n"] else 0.0
        last_iso = g["last_settled"].isoformat() if g["last_settled"] else None
        rows.append({
            "entity_type": etype,
            "entity_id": eid,
            "handle": g["name"] or str(eid),
            "avatar": g["avatar"],
            "region": region,
            "settled": g["settled"],
            "pending": g["pending"],
            "wins": g["wins"],
            "places": g["places"],
            "strike_rate": strike_rate(g["wins"], g["settled"]),
            "place_rate": strike_rate(g["places"], g["settled"]),
            "total_points": g["points"],
            "weekly_points": g["weekly_points"],
            "avg_points_per_tip": avg_pts,
            "form_rating": form_rating(
                avg_pts,
                player_avg_points if etype == "player" else site_avg_points,
            ),
            "value_index": value_index(avg_winner_sp, site_avg_winner_sp),
            "avg_winner_sp": avg_winner_sp,
            "qualified": qualifies(g["settled"], MIN_TIPS_TO_QUALIFY),
            # How many settled tips still separate this punter from the ranked
            # board, and whether they are "provisional" (playing, not yet counted).
            "needs": max(0, MIN_TIPS_TO_QUALIFY - g["settled"]),
            "provisional": etype == "player" and 0 < g["settled"] < MIN_TIPS_TO_QUALIFY,
            "decayed": (decayed(last_iso, now_iso) if last_iso else True) if etype == "player" else False,
            "last_settled": last_iso,
            "rank": None,
        })

    # Rank by form desc, then value desc, then total desc. Ties share a rank.
    rows.sort(key=lambda r: (r["form_rating"], r["value_index"], r["total_points"]), reverse=True)
    rank = 0
    prev_key = None
    for i, r in enumerate(rows, 1):
        key = (r["form_rating"], r["value_index"], r["total_points"])
        if key != prev_key:
            rank = i
            prev_key = key
        r["rank"] = rank

    return rows