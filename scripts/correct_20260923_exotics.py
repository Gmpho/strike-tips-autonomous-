"""One-off ledger correction — 2026-09-23 Durbanville exotics.

Context: the night's auto-settlement made two mistakes (both fixed in
result_tracker.py by commit 2aa14ed, deployed before this ran):
1. BIPOT:1-2-3-4-5-6 (20260923031126_BIP) was marked LOST on a false dead
   leg — winner "Captain's Elect" missed the 0.55 token fuzzy vs the
   apostrophe-stripped source spelling while the beaten savers matched.
   All 6 legs placed; official Bipot dividend R17.40/R1 (Raceform).
2. JACKPOT:5-6-7-8 (20260923031127_JAC) rightly WON but paid the R4-7
   pool's R496.50 (first same-type dividend row) instead of the R5-8
   pool's R2,257.40.

Run: modal run scripts/correct_20260923_exotics.py::correct
Safe: asserts abort before any write when state is unexpected; Modal
commits the volume only on successful completion.
"""

import modal

REPO = __file__.rsplit("/scripts/", 1)[0]

app = modal.App("ledger-correction-20260923")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("python-dotenv")
    .add_local_dir(REPO, "/app")
)
vol = modal.Volume.from_name("strike-tips-data", create_if_missing=False)

BIPOT_ID = "20260923031126_BIP"
BIPOT_DIV = 17.40
BIPOT_STAKE = 7.2
JAC_ID = "20260923031127_JAC"
JAC_DIV = 2257.40
JAC_STAKE = 4.8


@app.function(image=image, volumes={"/app/data": vol}, timeout=180)
def correct() -> dict:
    import sys

    sys.path.insert(0, "/app")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    out: dict = {}
    for bid in (BIPOT_ID, JAC_ID):
        b = next((x for x in gov._bets if x.bet_id == bid), None)
        assert b is not None, f"{bid} missing from ledger"
        out[bid] = (
            f"before: {b.status} stake={b.stake} "
            f"ret={b.actual_return} paper={b.is_paper}"
        )

    assert gov.void_settlement(
        BIPOT_ID,
        "manual correction 2026-09-23: false dead leg R1 apostrophe; all 6 legs placed",
    )
    assert gov.settle_exotic_bet(
        BIPOT_ID,
        round(BIPOT_DIV * BIPOT_STAKE, 2),
        "Manual correction 2026-09-23 (WON all 6 legs, tote dividend R17.40/R1)",
    )
    assert gov.void_settlement(
        JAC_ID,
        "manual correction 2026-09-23: wrong pool dividend R496.50 (R4-7 block)",
    )
    assert gov.settle_exotic_bet(
        JAC_ID,
        round(JAC_DIV * JAC_STAKE, 2),
        "Manual correction 2026-09-23 (WON all 4 legs, tote dividend R2257.40/R1)",
    )

    for bid in (BIPOT_ID, JAC_ID):
        b = next(x for x in gov._bets if x.bet_id == bid)
        out[bid] += f" -> after: {b.status} ret={b.actual_return} pnl={b.profit_loss}"
    out["paper_balance"] = gov.paper_balance
    out["done"] = True
    return out
