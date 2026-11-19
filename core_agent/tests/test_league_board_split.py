"""Two boards, one ledger (Nov-2026).

`/api/league/board?scope=all` used to return the AI cohorts and the
`StriketipsAI` account ranked among human punters. A cohort is built only
from settled wins, so it showed 100% strike rate above a punter's 14% — a
board that argues the machine beats you. Pinned here:

* `all` is humans only (cohorts and machine excluded);
* `system` is cohorts + machine only, with the ledger caveat attached;
* a `tier:` cohort exists only when the ledger really has more than one tier
  (every real bet is AUTO, so `region:SA` and `tier:AUTO` were the same 105
  bets at the same rank);
* cohorts decay like people do.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from core_agent.routes import league as lg
from core_agent.skills.league.rollups import is_system_entity


def _day(days_ago: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()


def _bet(**over):
    bet = {
        "track": "turffontein",
        "status": "WON",
        "stake": 10.0,
        "payout": 40.0,
        "odds": 4.0,
        "confidence": "AUTO",
        "date": _day(1),
        "placedAt": _day(1) + "T09:00:00",
    }
    bet.update(over)
    return bet


def _player_pick(entity_id: str, name: str, days_ago: int = 1):
    return {
        "entity_type": "player",
        "entity_id": entity_id,
        "entity_name": name,
        "region": "SA",
        "date": _day(days_ago),
        "settled": True,
        "won": True,
        "points": 12,
        "winner_sp": 4.0,
        "pick_odds": 4.0,
        "finish_position": 1,
    }


def _board(monkeypatch, bets, picks, **kwargs):
    """Call the route directly.

    `board()`'s defaults are FastAPI `Query` objects, so every parameter is
    passed explicitly — otherwise `ranked[:limit]` slices a Query instance.
    """
    monkeypatch.setattr(lg, "_load_bets", lambda: bets)
    monkeypatch.setattr(lg, "_load_user_picks", lambda: picks)
    params = {"region": None, "scope": "all", "sort": "form",
              "include_paper": False, "limit": 200}
    params.update(kwargs)
    return asyncio.run(lg.board(**params))


def _ids(payload):
    return {str(r["entity_id"]) for r in payload["all_rows"]}


def test_human_board_excludes_cohorts_and_machine(monkeypatch):
    bets = [_bet() for _ in range(6)]
    picks = [_player_pick("u_human", "Gift Mpho") for _ in range(6)]
    picks += [_player_pick("u_machine", "StriketipsAI") for _ in range(6)]

    payload = _board(monkeypatch, bets, picks, scope="all")
    ids = _ids(payload)

    assert payload["scope"] == "all"
    assert "u_human" in ids
    assert "u_machine" not in ids, "the machine account must never rank with punters"
    assert not any(i.startswith(("region:", "tier:", "track:")) for i in ids)
    assert all(r["system"] is False for r in payload["all_rows"])
    assert payload["population"]["human_entities"] == 1
    assert payload["population"]["system_entities"] >= 2  # region + track cohorts + machine
    assert "system_record" not in payload


def test_system_board_carries_its_own_caveat(monkeypatch):
    bets = [_bet() for _ in range(6)]
    bets += [_bet(status="EXPIRED", payout=0.0) for _ in range(3)]
    picks = [_player_pick("u_human", "Gift Mpho") for _ in range(6)]
    picks += [_player_pick("u_machine", "StriketipsAI") for _ in range(6)]

    payload = _board(monkeypatch, bets, picks, scope="system")
    ids = _ids(payload)

    assert payload["scope"] == "system"
    assert "u_human" not in ids
    assert "u_machine" in ids
    assert "region:SA" in ids
    assert "track:turffontein" in ids
    assert all(r["system"] is True for r in payload["all_rows"])

    record = payload["system_record"]
    assert record["settled"] == 6
    assert record["won"] == 6          # every settled real ticket won
    assert record["expired"] == 3
    assert record["unresolvedShare"] == 33.3
    assert record["lastSettled"] == _day(1)


def test_tier_cohort_only_when_tiers_differ(monkeypatch):
    """One AUTO tier is not a cohort — it was a duplicate of region:SA."""
    auto_only = _board(monkeypatch, [_bet() for _ in range(6)], [], scope="system")
    assert not any(i.startswith("tier:") for i in _ids(auto_only))

    mixed = [_bet(confidence="AUTO") for _ in range(3)]
    mixed += [_bet(confidence="VALUE") for _ in range(3)]
    payload = _board(monkeypatch, mixed, [], scope="system")
    ids = _ids(payload)
    assert "tier:AUTO" in ids
    assert "tier:VALUE" in ids


def test_cohorts_decay_like_players(monkeypatch):
    """A cohort whose last settled pick is a month old does not hold rank #1."""
    stale = [_bet(date=_day(30), placedAt=_day(30) + "T09:00:00") for _ in range(6)]
    payload = _board(monkeypatch, stale, [], scope="system")
    rows = [r for r in payload["all_rows"] if r["entity_id"] == "region:SA"]
    assert rows and rows[0]["decayed"] is True
    assert payload["ranked_rows"] == 0


def test_machine_handle_matches_however_it_is_cased():
    assert is_system_entity("player", "StriketipsAI") is True
    assert is_system_entity("player", "striketipsai") is True
    assert is_system_entity("player", "Strike Tips AI") is True
    assert is_system_entity("player", "Gift Mpho") is False
    # Cohort rows are system aggregates by construction.
    assert is_system_entity("cohort", "South Africa record") is True
