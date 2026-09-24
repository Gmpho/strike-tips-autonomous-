"""One-off ledger correction — 2026-09-24 Greyville R1 single.

Lilbitofmonica (20260924030934_LIL) was auto-settled WON (R949.92) on a
text-search false positive ("WINNER confirmed, confidence=100%"), but the
actual R1 result was: 1st Indignation, 2nd Cali Bullet, 3rd America
First — Lilbitofmonica ran 7th, 15L back. Void the phantom win and
record the truthful LOST (7th).

Run: modal run scripts/correct_20260924_lilbitofmonica.py::correct
Safe: asserts abort before any write when state is unexpected; Modal
commits the volume only on successful completion.
"""

import modal

REPO = __file__.rsplit("/scripts/", 1)[0]

app = modal.App("ledger-correction-20260924")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("python-dotenv")
    .add_local_file(
        f"{REPO}/core_agent/skills/bankroll_manager/governor.py",
        "/app/core_agent/skills/bankroll_manager/governor.py",
    )
    .add_local_file(
        f"{REPO}/core_agent/config/settings.py",
        "/app/core_agent/config/settings.py",
    )
)
vol = modal.Volume.from_name("strike-tips-data", create_if_missing=False)

BET_ID = "20260924030934_LIL"


@app.function(image=image, volumes={"/app/data": vol}, timeout=180)
def correct() -> dict:
    import sys

    sys.path.insert(0, "/app")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    b = next((x for x in gov._bets if x.bet_id == BET_ID), None)
    assert b is not None, f"{BET_ID} missing from ledger"
    out = {"before": f"{b.status} stake={b.stake} ret={b.actual_return} paper={b.is_paper}"}
    assert b.status == "WON", f"unexpected status {b.status} — aborting"

    assert gov.void_settlement(
        BET_ID,
        "manual correction 2026-09-24: phantom win, horse ran 7th (R1 won by Indignation)",
    )
    assert gov.settle_bet(
        BET_ID,
        won=False,
        notes="Manual correction 2026-09-24 (ran 7th of 10, 15L behind Indignation)",
        placed="7th",
    )

    b = next(x for x in gov._bets if x.bet_id == BET_ID)
    out["after"] = f"{b.status} ret={b.actual_return} pnl={b.profit_loss} placed={b.placed}"
    out["paper_balance"] = gov.paper_balance
    out["done"] = True
    return out
