"""Regression (Oct-2026, Greyville Friday night): the 10:39 PA sat 7/7 and
was buried LOST because R4-R8 legs evaluated against pre-race field
listings with no confirmed winner — matched names, no positions. Plus the
Gallic King Bipot was skipped as a "duplicate" of a stale losing ticket
because the dupe key ignored selections."""

import asyncio
import json
from types import SimpleNamespace

from core_agent.skills.bankroll_manager.governor import BankrollGovernor
from core_agent.skills import result_tracker as rt


def _combos(bankers):
    return [
        {"race": i + 1, "banker": b, "savers": ["Saver A", "Saver B"]}
        for i, b in enumerate(bankers)
    ]


def _ticket_bet(pool_type, legs, bankers, date="2026-10-09", track="greyville"):
    return SimpleNamespace(
        bet_id="TEST1",
        date=date,
        track=track,
        stake=7.20,
        horse=f"{pool_type}:" + "-".join(str(r) for r in legs),
        notes=json.dumps({
            "pool_type": pool_type,
            "pool_legs": legs,
            "combinations": [
                {"race": r, "banker": b, "savers": ["Saver A"]}
                for r, b in zip(legs, bankers)
            ],
            "ticket_cost": 1.2,
        }),
    )


def _races_with(pos_by_race):
    """ATR-shaped races: {race_number: [(name, position)]}."""
    out = []
    for rn, runners in pos_by_race.items():
        out.append({
            "title": f"{rn} 18:25",
            "runners": [{"name": n, "position": p} for n, p in runners],
        })
    return out


# ── Finality guard ────────────────────────────────────────────────────

def test_prerace_field_is_unknown_never_fail():
    """Legs evaluated against a field listing with no confirmed winner
    must stay PENDING (None) — never settle LOST."""
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("PA", [2, 3], ["Prophet", "Deonarie"])

        async def fake_races(*a, **k):
            return _races_with({
                2: [("Prophet", ""), ("Other One", "")],
                3: [("Deonarie", ""), ("Other Two", "")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append(a) or True,
        )
        rec = await tracker._settle_exotic_ticket(bet, gov, None)
        assert rec is None
        assert calls == []

    asyncio.run(go())


def test_winning_ticket_settles_won_with_dividend():
    """All legs placed + dividend available → WON with payout."""
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("PA", [2, 3], ["Prophet", "Deonarie"])

        async def fake_races(*a, **k):
            return _races_with({
                2: [("Prophet", "1st"), ("Other One", "2nd")],
                3: [("Deonarie", "1st"), ("Other Two", "3rd")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None

        async def fake_scrape(*a, **k):
            return None

        async def fake_div(*a, **k):
            return 38.80

        tracker._scrape_sa_results_direct = fake_scrape
        tracker._raceform_dividend = fake_div
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append((a, k)) or True,
        )
        rec = await tracker._settle_exotic_ticket(bet, gov, None)
        assert rec is not None
        assert calls and calls[0][0][1] == round(38.80 * 7.20, 2)

    asyncio.run(go())


def test_genuinely_dead_ticket_still_settles_lost():
    """Final data, winner confirmed but not on ticket → LOST (unchanged)."""
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("JACKPOT", [4], ["Rhydian"])

        async def fake_races(*a, **k):
            return _races_with({
                4: [("Globetonic", "1st"), ("Rhydian", "5th")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append(a) or True,
        )
        rec = await tracker._settle_exotic_ticket(bet, gov, None)
        assert rec is not None
        assert calls and calls[0][1] == 0.0

    asyncio.run(go())


# ── Selections-aware dupe key ─────────────────────────────────────────

def _gov(tmp_path):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    return BankrollGovernor(data_dir=str(d), starting_bankroll=1000.0)


def test_same_pool_legs_different_bankers_both_place(tmp_path):
    gov = _gov(tmp_path)
    combos_a = _combos(["Task Force", "Tiger Cody"])
    combos_b = _combos(["Gallic King", "Prophet"])
    a = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos_a, 1.2, 100.0)
    b = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos_b, 1.2, 100.0)
    assert a is not None and b is not None
    assert "Gallic King" in b.notes and "Task Force" in a.notes


def test_identical_ticket_still_skipped(tmp_path):
    gov = _gov(tmp_path)
    combos = _combos(["Gallic King", "Prophet"])
    a = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos, 1.2, 100.0)
    b = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos, 1.2, 100.0)
    assert a is not None and b is None


def test_label_variants_detected_as_same_ticket(tmp_path):
    gov = _gov(tmp_path)
    combos = _combos(["Deonarie", "Close Encounter"])
    a = gov.record_exotic_bet("greyville", "P6", [3, 4], combos, 1.2, 100.0)
    b = gov.record_exotic_bet("greyville", "PICK 6", [3, 4], combos, 1.2, 100.0)
    assert a is not None and b is None
