"""Regression (Oct-2026, Greyville Friday night): the 10:39 PA sat 7/7 and
was buried LOST because R4-R8 legs evaluated against pre-race field
listings with no confirmed winner — matched names, no positions. Plus the
Gallic King Bipot was skipped as a "duplicate" of a stale losing ticket
because the dupe key ignored selections."""

import asyncio
import json
from datetime import date as _date
from types import SimpleNamespace

from core_agent.skills.bankroll_manager.governor import BankrollGovernor
from core_agent.skills import result_tracker as rt


def _combos(bankers):
    return [
        {"race": i + 1, "banker": b, "savers": ["Saver A", "Saver B"]}
        for i, b in enumerate(bankers)
    ]


def _ticket_bet(pool_type, legs, bankers, date=None, track="greyville"):
    date = date or _date.today().isoformat()
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


# ── One-ticket-per-pool-per-day dupe key ──────────────────────────────

def _gov(tmp_path):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    return BankrollGovernor(data_dir=str(d), starting_bankroll=1000.0)


def test_same_pool_legs_different_bankers_second_skipped(tmp_path):
    """Oct-2026 policy reversal: exotic identity is (date, track, pool family,
    legs), so a later scan of the same pool+legs is skipped even with fresh
    bankers. Supersedes the earlier "different bankers = a new ticket" rule,
    which let the 05:00 and 09:30 scans both stay live on the same pool.
    """
    gov = _gov(tmp_path)
    combos_a = _combos(["Task Force", "Tiger Cody"])
    combos_b = _combos(["Gallic King", "Prophet"])
    a = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos_a, 1.2, 100.0)
    b = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos_b, 1.2, 100.0)
    assert a is not None and b is None
    # A different pool family on the same card is unaffected.
    p6 = gov.record_exotic_bet("greyville", "P6", [1, 2], combos_b, 1.2, 100.0)
    assert p6 is not None


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


# ── TAB favourite-substitution ──────────────────────────────────────

def test_scratched_banker_substitutes_snapshot_favourite():
    """Oct-2026 (Mohave Prince R7): scratched banker absent from results →
    snapshot favourite joins the leg; favourite placed → pass → WON."""
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("BIPOT", [7], ["Mohave Prince"])
        bet.notes = json.dumps({
            "pool_type": "BIPOT",
            "pool_legs": [7],
            "combinations": [{"race": 7, "banker": "Mohave Prince",
                              "savers": ["Pinot Grigio"]}],
            "ticket_cost": 1.2,
        })

        async def fake_races(*a, **k):
            return _races_with({
                7: [("Curious Girl", "2nd"), ("Pinot Grigio", "4th"),
                    ("Other One", "1st")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None
        import core_agent.skills.result_tracker as _rtmod
        _orig_fav = _rtmod._snapshot_favourite
        rt._snapshot_favourite = lambda *a, **k: "Curious Girl"

        async def fake_div(*a, **k):
            return 100.0

        tracker._scrape_sa_results_direct = fake_scrape_none
        tracker._raceform_dividend = fake_div
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append((a, k)) or True,
        )
        try:
            rec = await tracker._settle_exotic_ticket(bet, gov, None)
            assert rec is not None
            assert calls and calls[0][0][1] == round(100.0 * 7.20, 2)
        finally:
            _rtmod._snapshot_favourite = _orig_fav

    asyncio.run(go())


async def fake_scrape_none(*a, **k):
    return None


def test_scratched_leg_without_favourite_stays_open():
    """Pinot ran 4th (missed 1st/2nd) but Mohave never ran and the
    favourite is unfoundable: the sub may still have placed, so the leg
    (and ticket) stays PENDING with a loud flag — never failed on
    listed names alone."""
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("BIPOT", [7], ["Mohave Prince"])
        bet.notes = json.dumps({
            "pool_type": "BIPOT",
            "pool_legs": [7],
            "combinations": [{"race": 7, "banker": "Mohave Prince",
                              "savers": ["Pinot Grigio"]}],
            "ticket_cost": 1.2,
        })

        async def fake_races(*a, **k):
            return _races_with({
                7: [("Pinot Grigio", "4th"), ("Other One", "1st")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None
        import core_agent.skills.result_tracker as _rtmod2
        _orig_fav2 = _rtmod2._snapshot_favourite
        rt._snapshot_favourite = lambda *a, **k: None
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append((a, k)) or True,
        )
        try:
            rec = await tracker._settle_exotic_ticket(bet, gov, None)
            assert rec is None
            assert calls == []
        finally:
            _rtmod2._snapshot_favourite = _orig_fav2

    asyncio.run(go())


def test_tagged_notes_keep_ticket_json_through_settle(tmp_path):
    """Oct-2026 (Greyville AI Bipot): settling over void-tagged notes
    replaced the whole ticket object with a settlement-only stub, orphaning
    combos and leaving the ticket permanently unsettleable. Tagged notes
    must merge, never replace."""
    import json as _j
    gov = _gov(tmp_path)
    combos = _combos(["Gallic King", "Prophet"])
    placed = gov.record_exotic_bet("greyville", "BI1", [1, 2], combos, 1.2, 100.0)
    assert placed is not None
    # NOTE: record returns a detached copy — mutate the STORED record, as
    # the void path does in production.
    bet = next(b for b in gov._bets if b.bet_id == placed.bet_id)
    bet.notes = f"{bet.notes} | VOID (test tag)"
    assert gov.settle_exotic_bet(bet.bet_id, 0.0, "test settle") is True
    # Re-fetch: the atomic transaction reloads state from disk, so the
    # returned/stale handle does not observe the write.
    live = next(b for b in gov._bets if b.bet_id == placed.bet_id)
    assert live.status == "LOST"
    raw = str(live.notes)
    data = _j.loads(raw[: raw.rfind("}") + 1])
    assert data.get("pool_type") == "BI1", data.keys()
    assert len(data.get("combinations", [])) == 2
    assert data.get("settlement_notes") == "test settle"


def test_single_race_trifecta_needs_banker_first():
    """Oct-2026 (Greyville R4/R8): saver won but banker ran 4th — the
    ticket LOST its trifecta. Any-first would have paid it in full."""
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("TRIFECTA", [4], ["Champagne Mac"])
        bet.notes = json.dumps({
            "pool_type": "TRIFECTA", "pool_legs": [4],
            "combinations": [{"race": 4, "banker": "Champagne Mac",
                              "savers": ["Scandalize", "French War Lord"]}],
            "ticket_cost": 1.2})

        async def fake_races(*a, **k):
            return _races_with({
                4: [("French War Lord", "1st"), ("Lunch Money", "2nd"),
                    ("Scandalize", "3rd"), ("Champagne Mac", "4th")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append((a, k)) or True)
        rec = await tracker._settle_exotic_ticket(bet, gov, None)
        assert rec is not None
        assert calls and calls[0][0][1] == 0.0

    asyncio.run(go())


def test_single_race_exacta_banker_first_saver_second_wins():
    async def go():
        tracker = rt.ResultTracker()
        bet = _ticket_bet("EXACTA", [4], ["Champagne Mac"])
        bet.notes = json.dumps({
            "pool_type": "EXACTA", "pool_legs": [4],
            "combinations": [{"race": 4, "banker": "Champagne Mac",
                              "savers": ["Scandalize"]}],
            "ticket_cost": 1.2})

        async def fake_races(*a, **k):
            return _races_with({
                4: [("Champagne Mac", "1st"), ("Scandalize", "2nd")],
            })

        tracker._exotic_leg_races = fake_races
        tracker._race_off_datetime = lambda *a, **k: None

        async def fake_div(*a, **k):
            return 30.20

        tracker._scrape_sa_results_direct = fake_scrape_none
        tracker._raceform_dividend = fake_div
        calls = []
        gov = SimpleNamespace(
            settle_exotic_bet=lambda *a, **k: calls.append((a, k)) or True)
        rec = await tracker._settle_exotic_ticket(bet, gov, None)
        assert rec is not None
        assert calls and calls[0][0][1] == round(30.20 * 7.20, 2)

    asyncio.run(go())
