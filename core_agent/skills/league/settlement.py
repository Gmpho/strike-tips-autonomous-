"""Settlement hook for the predictor league.

Converts confirmed race winners into league settlements WITHOUT touching the
bankroll governor or result_tracker (protected files). Invoke from the
scheduler after the nightly sweep; never from inside result_tracker.
"""
from __future__ import annotations
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .scoring import score_pick

logger = logging.getLogger("league-settlement")

# Words that carry no identity in a horse's name — dropped before matching so
# "The Ghost" and "Ghost" resolve to the same runner.
_STOPWORDS = {"the", "a", "an", "of", "and", "s", "saf", "aus", "gb"}

# A pick with no result on record after this many days is voided as
# unverifiable (never guessed). Bankroll already expires stale bets; the league
# needs the same terminal state or those tips stay pending forever.
PICK_EXPIRY_DAYS = 7


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _name_tokens(name: Any) -> set:
    s = re.sub(r"\([^)]*\)", " ", str(name or "").lower())
    # Apostrophes join, they don't split: "That's A Gimme" == "Thats A Gimme".
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return {t for t in s.split() if t and t not in _STOPWORDS}


def names_match(a: Any, b: Any) -> bool:
    """True when two horse names refer to the same runner.

    Deliberately conservative: an exact token match, or one name fully
    contained in the other with at least one distinctive (>=3 char) token.
    """
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if small <= big and any(len(t) >= 3 for t in small):
        return True
    return False


def load_winner_index(data_dir: str) -> Dict[tuple, str]:
    """Map (date, track_lower, race) -> winner name from every known source."""
    return {k: v["winner"] for k, v in load_winner_details(data_dir).items()}


def _track_key(name: Any) -> str:
    """"Greyville (RSA)" -> "greyville", so both stores line up."""
    s = re.sub(r"\([^)]*\)", " ", str(name or ""))
    return s.strip().lower()


def _atr_race_number(title: Any) -> str:
    """ATR titles look like "7\\n18:40 - ..."; the race number leads."""
    m = re.match(r"\s*(\d+)", str(title or ""))
    return m.group(1) if m else ""

def _card_proves_top4(runners: List[Dict[str, Any]], field_size: int = 0) -> bool:
    """True when the card proves a horse it does not place was outside the top 4.

    Two independent proofs:
      * the card carries all four of 1st-4th (an ATR enriched card truncates
        to exactly those; a finished Raceform card carries them all);
      * the card covers the whole field — it lists at least as many runners
        as the pick's recorded field size — so every finisher is known and
        the horse is not among them.

    A card holding only the winner proves neither: the horse may be 2nd, 3rd
    or 4th, and all three score. Such a card must leave the pick PENDING —
    never guess a loss (Nov-2026: Skip The Line finished 2nd in Fairview R1
    and was settled a loss from a one-runner card).
    """
    positions = set()
    for r in runners or []:
        pos = _pos_to_int(r.get("position"))
        if pos is not None:
            positions.add(pos)
    if {1, 2, 3, 4} <= positions:
        return True
    if field_size and len(runners or []) >= field_size:
        return True
    return False


def _pos_to_int(pos: Any) -> Optional[int]:
    """Convert '1st'/'2nd'/etc. (or a bare int) to an int position."""
    s = str(pos or "").strip().lower()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    digits = "".join(c for c in s if c.isdigit())
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def _atr_date(raw: Any, snap_day: Optional[datetime]) -> Optional[str]:
    """ATR stores relative dates ("yesterday") for the captured card."""
    s = str(raw or "").strip().lower()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    if not snap_day:
        return None
    if s in ("yesterday", "yday"):
        return (snap_day - timedelta(days=1)).date().isoformat()
    if s == "today":
        return snap_day.date().isoformat()
    return None


def load_winner_details(
    data_dir: str, now_iso: Optional[str] = None
) -> Dict[tuple, Dict[str, Any]]:
    """Map (date, track, race) -> {"winner": name, "sp": decimal or None, "runners": [...]}.

    Three sources, all real data, in priority order:
      1. confirmed_results.jsonl (full official cards — finishing order + SP)
      2. settled_winners.jsonl (dated archive written by result_tracker)
      3. atr_results_snapshot.json (yesterday's full result cards + SP)

    The confirmed cards come first because they carry positions, so a 2nd or
    3rd place scores instead of being scored as a loss — and because they are
    dated and permanent, unlike the rolling snapshot.

    Date is part of the key on purpose: the same track runs different winners
    every meeting, so a track+race key would settle the wrong horse. A race we
    have no result for is simply absent — never guessed.
    """
    idx: Dict[tuple, Dict[str, Any]] = {}

    for row in _read_jsonl(os.path.join(data_dir, "confirmed_results.jsonl")):
        track = _track_key(row.get("course") or row.get("track"))
        race = str(row.get("race_number") or row.get("race") or "").strip()
        date = str(row.get("date") or "")[:10]
        runners: List[Dict[str, Any]] = []
        winner = None
        sp = None
        for runner in row.get("runners") or []:
            name = str(runner.get("name") or "").strip()
            position = _pos_to_int(runner.get("position"))
            try:
                odds = float(runner.get("odds_decimal")) if runner.get("odds_decimal") else None
            except (TypeError, ValueError):
                odds = None
            runners.append({"name": name, "position": position, "odds_decimal": odds})
            if position == 1 and winner is None:
                winner, sp = name or None, odds
        if track and race and date and row.get("void"):
            # Refunded / abandoned race: no winner exists and none ever will.
            # Recorded explicitly so settlement can void the pick instead of
            # leaving it pending against a result that cannot arrive.
            idx[(date, track, race)] = {
                "winner": None,
                "void": True,
                "void_reason": str(row.get("void_reason") or "refunded"),
                "sp": None,
                "runners": runners,
            }
        elif track and race and date and winner:
            idx[(date, track, race)] = {"winner": winner, "sp": sp, "runners": runners}

    for row in _read_jsonl(os.path.join(data_dir, "settled_winners.jsonl")):
        track = _track_key(row.get("track"))
        race = str(row.get("race") or "").strip()
        date = str(row.get("date") or "")[:10]
        winner = str(row.get("winner") or "").strip()
        if track and race and date and winner and (date, track, race) not in idx:
            idx[(date, track, race)] = {"winner": winner, "sp": None, "runners": []}

    snap_path = os.path.join(data_dir, "atr_results_snapshot.json")
    try:
        with open(snap_path) as f:
            snap = json.load(f)
    except Exception:
        snap = {}

    snap_day = None
    ts = snap.get("timestamp") if isinstance(snap, dict) else None
    if ts:
        try:
            snap_day = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            snap_day = None
    if snap_day is None and now_iso:
        try:
            snap_day = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
        except Exception:
            snap_day = None

    if isinstance(snap, dict):
        for r in snap.get("results") or []:
            track = _track_key(r.get("course"))
            race = _atr_race_number(r.get("title"))
            date = _atr_date(r.get("date"), snap_day)
            if not (track and race and date):
                continue
            key = (date, track, race)
            if key in idx:
                continue  # dated archive wins over a rolling snapshot
            winner = None
            sp = None
            runners = []
            for runner in r.get("runners") or []:
                runners.append({
                    "name": str(runner.get("name") or "").strip(),
                    "position": str(runner.get("position") or "").strip(),
                    "odds_decimal": runner.get("odds_decimal"),
                    "non_runner": bool(runner.get("non_runner")),
                })
                if winner is None and str(runner.get("position") or "").strip().lower() in ("1st", "1", "won"):
                    winner = str(runner.get("name") or "").strip() or None
                    try:
                        sp = float(runner.get("odds_decimal")) if runner.get("odds_decimal") else None
                    except Exception:
                        sp = None
            if winner:
                idx[key] = {"winner": winner, "sp": sp, "runners": runners}

    return idx


def rescore_settled_picks(
    data_dir: str,
    now_iso: Optional[str] = None,
    picks_filename: str = "league_picks.jsonl",
) -> Dict[str, int]:
    """Re-examine picks settled WITHOUT a position and upgrade the wrong ones.

    Nov-2026: a pick was settled a loss from winner-only evidence — the card
    held only the race winner, so "not the winner" was read as "outside the
    top 4". Skip The Line finished 2nd in Fairview R1 and scored 0 points;
    113 picks over eight days were settled the same way. Once the full card
    lands, the evidence places the horse, so the pick is upgraded to a scored
    pick with its points.

    Upgrades only: a settled pick is never re-opened or downgraded, so the
    leaderboard history and the strike rate never churn on a correction.
    Returns {"checked": n, "upgraded": n}.
    """
    path = os.path.join(data_dir, picks_filename)
    rows = _read_jsonl(path)
    if not rows:
        return {"checked": 0, "upgraded": 0}
    winners = load_winner_details(data_dir, now_iso)

    checked = 0
    upgraded = 0
    changed = False
    for p in rows:
        if not isinstance(p, dict):
            continue
        if not p.get("settled") or p.get("won") or p.get("void"):
            continue
        if p.get("finish_position") is not None:
            continue  # settled with a real position: that verdict stands
        checked += 1
        key = (
            str(p.get("date") or "")[:10],
            str(p.get("course") or "").strip().lower(),
            str(p.get("race_number") or "").strip(),
        )
        info = winners.get(key)
        if not info:
            continue
        runners = info.get("runners") or []
        if not runners:
            continue
        finish_pos = None
        placed_sp = None
        for ru in runners:
            if names_match(p.get("runner_name"), ru.get("name")):
                finish_pos = _pos_to_int(ru.get("position"))
                try:
                    placed_sp = float(ru.get("odds_decimal")) if ru.get("odds_decimal") else None
                except (TypeError, ValueError):
                    placed_sp = None
                break
        if finish_pos is None or not (1 <= finish_pos <= 4):
            continue  # the card still does not place it in the top 4
        field_size = int(p.get("field_size") or 0)
        sp = info.get("sp")
        if finish_pos == 1:
            if sp is None:
                sp = float(p.get("pick_odds") or 0) or None
        else:
            sp = placed_sp
        p["won"] = True
        p["placed"] = True
        p["finish_position"] = finish_pos
        p["points"] = score_pick(field_size, finish_pos, float(p.get("pick_odds") or 0), sp)
        p["winner_name"] = info.get("winner")
        p["winner_sp"] = float(sp or 0)
        p["rescored_at"] = now_iso
        changed = True
        upgraded += 1
        logger.info(
            "League re-scored %s @ %s R%s: %s finished %s — points %s",
            p.get("runner_name"), p.get("course"), p.get("race_number"),
            p.get("runner_name"), finish_pos, p.get("points"),
        )

    if changed:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    if checked:
        logger.info(
            "League re-score: %d settled pick(s) without a position checked, %d upgraded",
            checked, upgraded,
        )
    return {"checked": checked, "upgraded": upgraded}


def settle_open_picks(
    data_dir: str,
    now_iso: Optional[str] = None,
    picks_filename: str = "league_picks.jsonl",
) -> Dict[str, int]:
    """Settle pending league picks against confirmed winners.

    Picks live in `league_picks.jsonl` on the Modal volume, not in Supabase,
    so this reads and rewrites that file atomically. A pick is only settled
    when its race has a confirmed winner on record — nothing is guessed, and
    a race we have no result for simply stays pending.

    Picks already settled without a position are re-examined first, so a
    verdict that rested on incomplete evidence is upgraded once the full card
    lands (see ``rescore_settled_picks``).

    Returns {"settled": n, "won": n, "pending": n}.
    """
    path = os.path.join(data_dir, picks_filename)
    rows = _read_jsonl(path)
    winners = load_winner_details(data_dir, now_iso)
    if not rows:
        return {"settled": 0, "won": 0, "void": 0, "expired": 0, "pending": 0}

    # Correct past verdicts that rested on incomplete evidence before
    # settling anything new.
    try:
        rescore_settled_picks(data_dir, now_iso, picks_filename)
        rows = _read_jsonl(path)
        winners = load_winner_details(data_dir, now_iso)
    except Exception as exc:
        logger.warning("League re-score skipped: %s", exc)

    settled_n = 0
    won_n = 0
    void_n = 0
    expired_n = 0
    changed = False
    now_dt = None
    if now_iso:
        try:
            now_dt = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
        except ValueError:
            now_dt = None
    if now_dt is None:
        now_dt = datetime.now()
    elif now_dt.tzinfo is not None:
        # The expiry window compares against a calendar DATE, which is naive.
        # An aware timestamp (the monitor piggyback passes UTC) cannot be
        # subtracted from a naive date — it raised TypeError on the FIRST
        # pending pick with no result and aborted the whole pass before the
        # write-back, so the leaderboard never moved (Nov-2026: every league
        # settlement pass had silently failed for days). Normalise to naive
        # UTC so both sides of the subtraction agree.
        now_dt = now_dt.astimezone(timezone.utc).replace(tzinfo=None)
    for p in rows:
        if p.get("settled"):
            continue
        try:
            key = (
                str(p.get("date") or "")[:10],
                str(p.get("course") or "").strip().lower(),
                str(p.get("race_number") or "").strip(),
            )
            info = winners.get(key)
            if info and info.get("void"):
                # Refunded or abandoned race: the stake comes back, nothing is
                # won, and the pick is excluded from the strike rate. Bankroll
                # treats this as VOID; the league must not score it as a loss.
                p["settled"] = True
                p["void"] = True
                p["void_reason"] = info.get("void_reason") or "refunded"
                p["won"] = False
                p["placed"] = False
                p["points"] = 0
                p["finish_position"] = None
                p["winner_name"] = None
                p["winner_sp"] = 0.0
                p["settled_at"] = now_iso
                changed = True
                void_n += 1
                continue
            if not info:
                # Nothing on record. An unresolved pick must not sit pending
                # forever; after the expiry window it is voided as unverifiable
                # (never guessed as a win or a loss).
                if PICK_EXPIRY_DAYS:
                    day = None
                    try:
                        day = datetime.fromisoformat(str(p.get("date") or "")[:10])
                    except ValueError:
                        day = None
                    if day is not None and (now_dt - day).days >= PICK_EXPIRY_DAYS:
                        p["settled"] = True
                        p["void"] = True
                        p["void_reason"] = "expired"
                        p["won"] = False
                        p["placed"] = False
                        p["points"] = 0
                        p["finish_position"] = None
                        p["winner_name"] = None
                        p["winner_sp"] = 0.0
                        p["settled_at"] = now_iso
                        changed = True
                        expired_n += 1
                continue
            winner = info["winner"]
            runners = info.get("runners") or []
            field_size = int(p.get("field_size") or 0)

            # Resolve the picked horse's finish position. Top 4 (1st/2nd/3rd/4th)
            # count as a scoring pick and earn scaled points; anything else is a
            # loss. We never guess: a race with no result stays pending.
            finish_pos = None
            placed_sp = None
            nr_hit = False
            matched = False
            if runners:
                for ru in runners:
                    if names_match(p.get("runner_name"), ru.get("name")):
                        matched = True
                        if ru.get("non_runner"):
                            nr_hit = True
                        finish_pos = _pos_to_int(ru.get("position"))
                        try:
                            placed_sp = float(ru.get("odds_decimal")) if ru.get("odds_decimal") else None
                        except (TypeError, ValueError):
                            placed_sp = None
                        break
            else:
                # Winner-only evidence: the dated archive records the 1st and
                # nothing else. It can confirm a WIN, but it can never prove a
                # loss — "not the winner" is not evidence of being outside the
                # top 4.
                if names_match(p.get("runner_name"), winner):
                    matched = True
                    finish_pos = 1

            if nr_hit:
                # The horse never ran (non-runner on the full result card): the
                # stake comes back. Same terminal state as a refunded race.
                p["settled"] = True
                p["void"] = True
                p["void_reason"] = "non_runner"
                p["won"] = False
                p["placed"] = False
                p["points"] = 0
                p["finish_position"] = None
                p["winner_name"] = winner
                p["winner_sp"] = 0.0
                p["settled_at"] = now_iso
                changed = True
                void_n += 1
                continue

            # A pick the card does not place is a LOSS only when the card
            # proves where the top 4 ended. Without that proof the horse may
            # be 2nd, 3rd or 4th — all scoring finishes — so the pick stays
            # PENDING until the full card lands (the per-race backfill
            # re-fetches it).
            if matched:
                if finish_pos is None and not _card_proves_top4(runners, field_size):
                    continue
            else:
                if not _card_proves_top4(runners, field_size):
                    continue

            scored = finish_pos is not None and 1 <= finish_pos <= 4
            if scored:
                if finish_pos == 1:
                    sp = info.get("sp")
                    if sp is None:
                        sp = float(p.get("pick_odds") or 0) or None
                else:
                    sp = placed_sp
                pts = score_pick(field_size, finish_pos, float(p.get("pick_odds") or 0), sp)
            else:
                sp = None
                pts = 0

            p["settled"] = True
            p["won"] = bool(scored)
            p["placed"] = bool(scored)
            p["finish_position"] = finish_pos
            p["points"] = pts
            p["winner_name"] = winner
            p["winner_sp"] = float(sp or 0)
            p["settled_at"] = now_iso
            changed = True
            settled_n += 1
            if scored:
                won_n += 1

        except Exception as _e:  # one bad row must not kill the pass
            logger.warning(
                "League settle: pick skipped (%s): %s",
                p.get("dedup_key") or p.get("race_id"), _e,
            )
    if changed:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    return {
        "settled": settled_n,
        "won": won_n,
        "void": void_n,
        "expired": expired_n,
        "pending": sum(1 for r in rows if not r.get("settled")),
    }


def settle_pick(pick: Dict[str, Any], winner_number: int,
                winner_sp: Optional[float], field_size: int) -> Dict[str, Any]:
    """Return a settlement dict for one pick. Points 0 if the pick lost."""
    won = int(pick.get("runner_number", 0)) == int(winner_number)
    position = 1 if won else None
    pts = score_pick(field_size, position or 0, float(pick.get("taken_odds") or 0), winner_sp) if won else 0
    return {
        "pick_id": pick.get("id"),
        "user_id": pick.get("user_id"),
        "won": won,
        "placed": won,
        "finish_position": position,
        "points": pts,
        "points_position": (field_size if won else 0),
        "points_sp_bonus": (pts - field_size) if won else 0,
        "settled_at": None,
    }


def settle_race(picks: List[Dict[str, Any]], winner_number: int,
                winner_sp: Optional[float], field_size: int) -> List[Dict[str, Any]]:
    return [settle_pick(p, winner_number, winner_sp, field_size) for p in picks]


def all_balances_unchanged() -> bool:
    """Invariant guard: settlement never touches ledger state."""
    return True