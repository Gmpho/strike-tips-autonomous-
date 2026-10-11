"""One-shot admin tasks (Oct-2026): void a wrongfully-settled ticket so the
fixed settler re-evaluates it. Separate file so modal_app.py stays untouched.
Run: modal run core_agent/core/admin_tasks.py::void_ticket --bet-id <id>
"""

import modal

app = modal.App("strike-tips-admin")

# Same baked image as the main app so core_agent imports work.
image = modal.Image.from_dockerfile("Dockerfile")
data_volume = modal.Volume.from_name("strike-tips-data", create_if_missing=True)
secrets = [modal.Secret.from_name("strike-tips-secrets")]


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def void_ticket(bet_id: str, notes: str = "") -> dict:
    """Reverse a wrongful settlement (bet → PENDING + refund)."""
    import os
    import sys

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    ok = gov.void_settlement(bet_id, notes or "admin reversal of wrongful settle")
    return {"bet_id": bet_id, "voided": ok}


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def cancel_ticket(bet_id: str, notes: str = "") -> dict:
    """Cancel a PENDING ticket (VOID + stake refund)."""
    import os
    import sys

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    ok = gov.cancel_pending_bet(bet_id, notes or "admin cancel")
    return {"bet_id": bet_id, "cancelled": ok}


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def check_ticket(bet_id: str) -> dict:
    """Read-only: current status/payout/notes of one bet."""
    import os
    import sys

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    bet = next((b for b in gov._bets if b.bet_id == bet_id), None)
    import json as _j

    if not bet:
        print(_j.dumps({"bet_id": bet_id, "found": False}))
        return {"bet_id": bet_id, "found": False}
    out = {
        "bet_id": bet_id,
        "found": True,
        "status": bet.status,
        "actual_return": getattr(bet, "actual_return", None),
        "profit_loss": getattr(bet, "profit_loss", None),
        "is_paper": getattr(bet, "is_paper", None),
        "notes_tail": str(getattr(bet, "notes", "") or "")[-160:],
    }
    print(_j.dumps(out, default=str))
    return out


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def repair_notes(bet_id: str, notes_json: str) -> dict:
    """Rewrite a bet's notes with a full ticket object (plus preserved
    history tags). Used when a settle/void cycle orphaned combos."""
    import os
    import sys
    import json as _j

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    bet = next((b for b in gov._bets if b.bet_id == bet_id), None)
    if not bet:
        print(_j.dumps({"bet_id": bet_id, "found": False}))
        return {"bet_id": bet_id, "found": False}
    with gov._atomic_transaction():
        live = next((b for b in gov._bets if b.bet_id == bet_id), None)
        if live is None:
            print(_j.dumps({"bet_id": bet_id, "found": False}))
            return {"bet_id": bet_id, "found": False}
        prior = str(live.notes or "")
        tags = ""
        if "| VOID" in prior:
            tags = prior[prior.find("| VOID"):]
        data = _j.loads(notes_json)
        live.notes = _j.dumps(data) + (f" {tags}" if tags else "")
    print(_j.dumps({"bet_id": bet_id, "repaired": True,
                    "status": live.status}))
    return {"bet_id": bet_id, "repaired": True}
