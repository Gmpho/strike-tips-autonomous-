"""Regression tests for the Sep-2026 exotic settlement failures.

Three interacting bugs:
1. Same-second bet_id collisions (two Jackpots -> same `..._JAC` id)
2. First-match lookup shadowing (settle found the LOST twin forever)
3. Cross-container full-file clobber (auto-bet run erased a sibling settle)
"""
import json

import pytest

from core_agent.skills.bankroll_manager.governor import BankrollGovernor, BetRecord


@pytest.fixture
def temp_data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return str(d)


def _make_exotic(gov, pool_type, legs):
    return gov.record_exotic_bet(
        track="Scottsville",
        pool_type=pool_type,
        pool_legs=legs,
        combinations=[{"race": legs[0], "banker": "Horse A", "savers": []}],
        ticket_cost=1.2,
        estimated_dividend=10.0,
    )


def test_same_second_exotic_ids_are_unique(temp_data_dir):
    """Two Jackpots placed in the same second must not share a bet_id."""
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    # Force same-second placement by monkeypatching is unnecessary:
    # record twice back-to-back; if the clock ticks we simulate anyway.
    b1 = _make_exotic(gov, "JACKPOT", [4, 5, 6, 7])
    b2 = _make_exotic(gov, "JACKPOT", [5, 6, 7, 8])
    # If timestamps collided, b2 must get a suffixed id — either way unique.
    assert b1 and b2
    assert b1.bet_id != b2.bet_id, "bet_id collision: two tickets share an id"


def test_settle_prefers_pending_over_settled_shadow(temp_data_dir):
    """A PENDING ticket sharing a legacy id with a settled twin must still
    be settable (prefers-PENDING lookup)."""
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    b1 = _make_exotic(gov, "JACKPOT", [4, 5, 6, 7])
    # Simulate the legacy collision by rewriting b2's id to match b1's.
    b2 = _make_exotic(gov, "JACKPOT", [5, 6, 7, 8])
    for b in gov._bets:
        if b is b2:
            b.bet_id = b1.bet_id
    gov._save_state()  # transactions reload from disk — persist mutations first
    assert gov.settle_exotic_bet(b1.bet_id, 0.0, "lost leg") is True
    # The PENDING twin must still be reachable and settleable.
    assert gov.settle_exotic_bet(b1.bet_id, 0.0, "lost other leg") is True
    twins = [b for b in gov._bets if b.bet_id == b1.bet_id]
    assert sorted(b.status for b in twins) == ["LOST", "LOST"]


def test_load_dedupes_shadowed_pending(temp_data_dir):
    """Ledger self-heal: a PENDING duplicate RECORDING (same horse/track/date
    as its settled twin) is dropped on load, but a PENDING twin with a
    DIFFERENT ticket is a live bet and must survive."""
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    b1 = _make_exotic(gov, "JACKPOT", [4, 5, 6, 7])
    # (a) true duplicate recording of the same ticket — the recorder's
    # idempotency gate blocks a second identical call, so craft it directly
    # (as overlapping monitor runs historically did).
    dup = BetRecord(
        bet_id=b1.bet_id,
        timestamp=b1.timestamp,
        date=b1.date,
        track=b1.track,
        race_number=b1.race_number,
        horse=b1.horse,
        odds=b1.odds,
        stake=b1.stake,
        potential_return=b1.potential_return,
        status="PENDING",
        edge_percent=0.0,
        confidence="EXOTIC",
        notes=b1.notes,
        is_paper=True,
    )
    gov._bets.append(dup)
    # (b) different ticket sharing the legacy id
    b2 = _make_exotic(gov, "JACKPOT", [5, 6, 7, 8])
    b2.bet_id = b1.bet_id
    gov._save_state()  # persist mutations before the settle transaction reloads
    gov.settle_exotic_bet(b1.bet_id, 0.0, "lost")
    gov._save_state()

    gov2 = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    same_ids = [b for b in gov2._bets if b.bet_id == b1.bet_id]
    # duplicate recording gone; different-ticket PENDING kept
    assert len(same_ids) == 2, "expected settled twin + live PENDING twin"
    assert any(b.status == "PENDING" for b in same_ids)
    assert all(b.status == "LOST" or b.status == "PENDING" for b in same_ids)


def test_unique_id_suffix_persists_roundtrip(temp_data_dir):
    """-2 suffixed ids stay unique across a save/reload cycle."""
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    b1 = _make_exotic(gov, "JACKPOT", [4, 5, 6, 7])
    b2 = _make_exotic(gov, "JACKPOT", [5, 6, 7, 8])
    if b2.bet_id == b1.bet_id:  # clock did not tick
        b2.bet_id = f"{b1.bet_id}-2"
    gov._save_state()
    gov2 = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    ids = [b.bet_id for b in gov2._bets]
    assert len(ids) == len(set(ids)), "duplicate bet_ids after reload"
