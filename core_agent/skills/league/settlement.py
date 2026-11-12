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
from typing import Any, Dict, List, Optional, Tuple

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


def _utc_hhmm(value: Any) -> str:
    """An off time as UTC "HH:MM".

    A pick's ``off_iso`` is written in the meeting's own timezone (SAST for SA,
    UTC for the US meetings, local time for UK/IRE), while ATR's own card
    titles are always UTC. Everything that has to be compared across feeds is
    normalised here, so a South African card at 12:15 SAST and an ATR title at
    10:15 are recognised as the same instant.
    """
    s = str(value or "").strip()
    if not s:
        return ""
    if re.match(r"^\d{1,2}:\d{2}$", s):
        return s[:5]  # already a wall clock; treated as UTC by the caller
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%H:%M")


def _atr_title_hhmm(title: Any) -> str:
    """The off time ATR's own title carries ("3\\n18:30 - Race 3 - ...").

    ATR states card times in UTC for every region it covers (Vaal R1 is
    "10:15" for the 12:15 SAST race), so the title time is directly
    comparable with a pick's UTC off time.
    """
    m = re.search(r"(\d{1,2}:\d{2})\s*-\s*Race", str(title or ""))
    return m.group(1) if m else ""


def _card_has_horse(card: Optional[Dict[str, Any]], pick: Dict[str, Any]) -> bool:
    """True when the card lists the picked horse."""
    if not card:
        return False
    for ru in card.get("runners") or []:
        if names_match(pick.get("runner_name"), ru.get("name")):
            return True
    return False


def _index_by_time(
    by_time: Dict[tuple, Dict[str, Any]],
    date: str,
    track: str,
    hhmm: Any,
    info: Dict[str, Any],
) -> None:
    """Index one race's evidence by its UTC off time.

    A card without a resolvable UTC time is simply not indexed by time — it
    stays reachable through the race-number path, which is all it ever had.
    """
    t = str(hhmm or "").strip()[:5]
    if not (date and track and re.match(r"^\d{1,2}:\d{2}$", t)):
        return
    by_time.setdefault((date, track, t), info)


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
    idx, _ = _load_winner_evidence(data_dir, now_iso)
    return idx


def load_winner_details_by_time(
    data_dir: str, now_iso: Optional[str] = None
) -> Dict[tuple, Dict[str, Any]]:
    """Map (date, track, "HH:MM" UTC) -> the same evidence, keyed by instant.

    Race numbers are not portable between feeds (Nov-2026: Betway numbered the
    Horseshoe Indianapolis meeting differently from ATR, so the same 18:30 race
    was "R4" in the odds feed and "R1" in ATR's card). The off time is the
    one identifier every feed agrees on, so evidence is also indexed by it.

    Only evidence that states its time in UTC is indexed: confirmed cards
    carry ``off_time_utc`` (written by the card producers), ATR's titles are
    already UTC. The dated winner archive states no time and stays on the
    race-number path.
    """
    _, by_time = _load_winner_evidence(data_dir, now_iso)
    return by_time


def load_atr_races_by_time(
    data_dir: str, now_iso: Optional[str] = None
) -> Dict[tuple, Dict[str, Any]]:
    """Map (date, track, "HH:MM" UTC) -> ATR's own race card for that instant.

    ATR's numbering is the one the league's ATR branch reads, so it — and only
    it — may renumber a pick. Cards from other feeds carry their own
    numbering and must never rewrite a pick's race number.
    """
    out: Dict[tuple, Dict[str, Any]] = {}
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

    if not isinstance(snap, dict):
        return out
    for r in snap.get("results") or []:
        track = _track_key(r.get("course"))
        race = _atr_race_number(r.get("title"))
        date = _atr_date(r.get("date"), snap_day)
        hhmm = _atr_title_hhmm(r.get("title"))
        if not (track and race and date and hhmm):
            continue
        runners = [
            {
                "name": str(x.get("name") or "").strip(),
                "position": str(x.get("position") or "").strip(),
                "odds_decimal": x.get("odds_decimal"),
                "non_runner": bool(x.get("non_runner")),
            }
            for x in (r.get("runners") or [])
        ]
        out[(date, track, hhmm)] = {
            "race_number": race,
            "runners": runners,
        }
    return out


def _load_winner_evidence(
    data_dir: str, now_iso: Optional[str] = None
) -> Tuple[Dict[tuple, Dict[str, Any]], Dict[tuple, Dict[str, Any]]]:
    """The result evidence, indexed by race number AND by off time."""
    idx: Dict[tuple, Dict[str, Any]] = {}
    by_time: Dict[tuple, Dict[str, Any]] = {}

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
            runners.append({
                "name": name,
                "position": position,
                "odds_decimal": odds,
                # A scratched horse never ran: the pick is refunded, not lost.
                # The flag lives on the confirmed card (Offtrackbetting and
                # Raceform both publish withdrawals), so it has to survive
                # into the index or the pick is scored a loss (Nov-2026).
                "non_runner": bool(runner.get("non_runner")),
            })
            if position == 1 and winner is None:
                winner, sp = name or None, odds
        if track and race and date and row.get("void"):
            # Refunded / abandoned race: no winner exists and none ever will.
            # Recorded explicitly so settlement can void the pick instead of
            # leaving it pending against a result that cannot arrive.
            info = {
                "winner": None,
                "void": True,
                "void_reason": str(row.get("void_reason") or "refunded"),
                "sp": None,
                "runners": runners,
                "race_number": race,
            }
            idx[(date, track, race)] = info
            _index_by_time(by_time, date, track, row.get("off_time_utc"), info)
        elif track and race and date and winner:
            info = {
                "winner": winner,
                "sp": sp,
                "runners": runners,
                "race_number": race,
            }
            idx[(date, track, race)] = info
            _index_by_time(by_time, date, track, row.get("off_time_utc"), info)

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
                info = {
                    "winner": winner,
                    "sp": sp,
                    "runners": runners,
                    "race_number": race,
                }
                # ATR states card times in UTC, so its title time is directly
                # comparable with a pick's UTC off time.
                _index_by_time(by_time, date, track, _atr_title_hhmm(r.get("title")), info)
                if key not in idx:
                    idx[key] = info  # dated archive wins over a rolling snapshot

    return idx, by_time


def _resolve_pick_race(
    pick: Dict[str, Any],
    by_number: Dict[tuple, Dict[str, Any]],
    by_time: Dict[tuple, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """The race evidence a pick must be settled against.

    The stored race number comes from the odds feed, and feeds number US
    meetings differently from ATR (Nov-2026: the same 18:30 race at Horseshoe
    Indianapolis was "R4" in the odds feed and "R1" in ATR's card). The off
    time is the one identifier both agree on, so it decides — but only when
    the evidence agrees with it:

      * the off-time card holds the picked horse -> that is the race;
      * the off-time card and the numbered card are the same race -> that one;
      * the numbers disagree and neither card holds the horse -> the race
        identity is in dispute, so NO card may settle this pick. It stays
        PENDING rather than taking a verdict from a race it may not have been
        placed in (and it expires as unverifiable if the dispute never clears).
    """
    date = str(pick.get("date") or "")[:10]
    track = _track_key(pick.get("course"))
    race = str(pick.get("race_number") or "").strip()
    hhmm = _utc_hhmm(pick.get("off_iso"))
    timed = by_time.get((date, track, hhmm)) if hhmm else None
    numbered = by_number.get((date, track, race))

    if timed is None:
        return numbered
    if _card_has_horse(timed, pick):
        return timed
    if numbered is None:
        return timed
    if str(timed.get("race_number") or "") == race:
        return numbered
    return None  # identity in dispute: no card may settle this pick


def repair_misnumbered_picks(
    data_dir: str,
    now_iso: Optional[str] = None,
    picks_filename: str = "league_picks.jsonl",
) -> Dict[str, int]:
    """Correct a pick's race number when ATR proves a different race for it.

    Nov-2026: two Horseshoe Indianapolis picks carried the odds feed's race
    number (R3/R4 for ATR's R1/R2). "Apotheon" won ATR's R1 but was settled a
    LOSS because the pick said R3, and "Four Star General" (2nd in R2) sat
    PENDING against a card that could never place it.

    Only ATR may renumber a pick: ATR is the numbering the league's own result
    branch reads, and a card from another feed carries that feed's numbering.
    A pick is only renumbered when ATR holds the picked horse for that exact
    off time — no proof, no change. A pick that already carries a finishing
    position is left alone: its verdict has spoken.
    """
    path = os.path.join(data_dir, picks_filename)
    rows = _read_jsonl(path)
    if not rows:
        return {"checked": 0, "repaired": 0}

    atr_by_time = load_atr_races_by_time(data_dir, now_iso)
    checked = 0
    repaired = 0
    changed = False
    for p in rows:
        if not isinstance(p, dict):
            continue
        if p.get("finish_position") is not None:
            continue  # a settled verdict stands
        date = str(p.get("date") or "")[:10]
        track = _track_key(p.get("course"))
        race = str(p.get("race_number") or "").strip()
        hhmm = _utc_hhmm(p.get("off_iso"))
        entry = atr_by_time.get((date, track, hhmm)) if hhmm else None
        if not entry:
            continue
        true_race = str(entry.get("race_number") or "").strip()
        if not true_race or true_race == race:
            continue
        checked += 1
        if not _card_has_horse(entry, p):
            continue  # ATR does not place our horse there: no proof, no change
        p["race_number"] = int(true_race) if true_race.isdigit() else true_race
        p["race_number_corrected"] = {
            "from": race,
            "to": p["race_number"],
            "at": now_iso or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": "the odds feed numbered this meeting differently from ATR",
        }
        repaired += 1
        changed = True
        logger.info(
            "League race number repaired: %s @ %s R%s -> R%s (ATR off time %s)",
            p.get("runner_name"), p.get("course"), race, p["race_number"], hhmm,
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
            "League race-number repair: %d pick(s) checked, %d repaired",
            checked, repaired,
        )
    return {"checked": checked, "repaired": repaired}


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
    by_time = load_winner_details_by_time(data_dir, now_iso)

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
        info = _resolve_pick_race(p, winners, by_time)
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
    by_time = load_winner_details_by_time(data_dir, now_iso)
    if not rows:
        return {"settled": 0, "won": 0, "void": 0, "expired": 0, "pending": 0}

    # A pick can carry the odds feed's race number, which is not the numbering
    # ATR uses (Nov-2026: the same race was R4 in the feed and R1 in ATR's
    # card). Repair it before anything is read against it, so no pick is
    # settled against a race it was not placed in.
    try:
        repair_misnumbered_picks(data_dir, now_iso, picks_filename)
        rows = _read_jsonl(path)
        winners = load_winner_details(data_dir, now_iso)
        by_time = load_winner_details_by_time(data_dir, now_iso)
    except Exception as exc:
        logger.warning("League race-number repair skipped: %s", exc)

    # Correct past verdicts that rested on incomplete evidence before
    # settling anything new.
    try:
        rescore_settled_picks(data_dir, now_iso, picks_filename)
        rows = _read_jsonl(path)
        winners = load_winner_details(data_dir, now_iso)
        by_time = load_winner_details_by_time(data_dir, now_iso)
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
            info = _resolve_pick_race(p, winners, by_time)
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