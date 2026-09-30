"""One-off: void malformed/wrong-leg Fairview exotic tickets (2026-09-30).

- BI1:2-3, JP1:4-5-6: unscorable (missing legs, no TAB pool).
- PA 2-8, PICK6 3-8, JP 4-7: wrong legs (TAB 9-race standard is
  PA 3-9, P6 4-9, JP 5-8). Correct BIPOT R2-7 + JP R6-9 stay live.
Run: modal run scripts/void_fairview_malformed.py::void_bad
"""
import modal

app = modal.App("ledger-void-fairview-0930")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("python-dotenv")
    .add_local_file(
        "core_agent/skills/bankroll_manager/governor.py",
        "/app/core_agent/skills/bankroll_manager/governor.py",
    )
    .add_local_file(
        "core_agent/config/settings.py",
        "/app/core_agent/config/settings.py",
    )
)
vol = modal.Volume.from_name("strike-tips-data", create_if_missing=False)

BAD_IDS = [
    "20260930031106_BI1",
    "20260930031107_JAC",
    "20260930060817_PLA",
    "20260930060817_PIC",
    "20260930060817_JAC",
]


@app.function(image=image, volumes={"/app/data": vol}, timeout=180)
def void_bad() -> dict:
    import sys

    sys.path.insert(0, "/app")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    out: dict = {}
    for bid in BAD_IDS:
        b = next((x for x in gov._bets if x.bet_id == bid), None)
        if b is None:
            out[bid] = "missing"
            continue
        if b.status != "PENDING":
            out[bid] = f"skip (status {b.status})"
            continue
        ok = gov.cancel_pending_bet(
            bid, "voided 2026-09-30: malformed/wrong legs (no such TAB pool)"
        )
        out[bid] = f"voided={ok} stake={b.stake}"
    out["done"] = True
    return out
