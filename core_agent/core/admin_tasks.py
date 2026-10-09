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
