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
    data_volume.commit()
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
    data_volume.commit()
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
    data_volume.commit()
    print(_j.dumps({"bet_id": bet_id, "repaired": True,
                    "status": live.status}))
    return {"bet_id": bet_id, "repaired": True}


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def expire_old_bets(max_age_days: int = 3) -> dict:
    """One-shot backlog hygiene: EXPIRE all PENDING bets older than N days.
    No money moves (stakes already sunk); clears fossils the nightly
    settle loop never reaches."""
    import os
    import sys
    import json as _j
    from datetime import date as _date

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    # Pull the latest committed volume state first: a fresh container mounts a
    # snapshot, but a long-lived sibling may have committed since (Oct-2026).
    try:
        data_volume.reload()
    except Exception:
        pass

    gov = BankrollGovernor(data_dir="/app/data")
    today = _date.today()
    expired = []
    # Flip rows DIRECTLY inside one transaction. expire_stale_bet() looks the
    # bet up by id, but bet_history can hold duplicate ids (a settled row plus
    # a live PENDING row) — that lookup hits the settled twin and no-ops while
    # still returning True (Oct-2026: 18 "expired" that never moved).
    with gov._atomic_transaction():
        for b in gov._bets:
            if b.status != "PENDING":
                continue
            # Age from date, falling back to placedAt timestamp (Oct-2026:
            # bets with missing/unparseable dates dodged expiry forever).
            age = None
            for src in (getattr(b, "date", None),
                        str(getattr(b, "timestamp", "") or "")[:10]):
                try:
                    age = (today - _date.fromisoformat(str(src or "")[:10])).days
                    break
                except (ValueError, TypeError):
                    continue
            if age is not None and age > max_age_days:
                b.status = "EXPIRED"
                expired.append(b.bet_id)
    # Modal Volumes only persist writes to other containers after commit().
    data_volume.commit()
    out = {"expired": len(expired), "bet_ids": expired}
    print(_j.dumps(out))
    return out


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def stamp_file(path: str, content: str) -> dict:
    """Write a small stamp file under /app/data (scheduler coordination)."""
    import os
    import sys
    import json as _j

    sys.path.insert(0, "/app")
    full = os.path.join("/app/data", path.lstrip("/"))
    if not full.startswith("/app/data/"):
        print(_j.dumps({"written": False, "reason": "path escape"}))
        return {"written": False}
    with open(full, "w") as f:
        f.write(content)
    data_volume.commit()
    print(_j.dumps({"written": True, "path": path}))
    return {"written": True}


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def rename_bet(bet_id: str, new_bet_id: str, race_number: int = 0) -> dict:
    """Give a shadowed (duplicate-ID) bet a unique ID so it becomes
    settleable/voidable again. Refuses if the target ID already exists."""
    import os
    import sys
    import json as _j

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir="/app/data")
    with gov._atomic_transaction():
        if any(b.bet_id == new_bet_id for b in gov._bets):
            print(_j.dumps({"renamed": False, "reason": "target exists"}))
            return {"renamed": False}
        matches = [b for b in gov._bets if b.bet_id == bet_id]
        if race_number:
            matches = [b for b in matches
                       if getattr(b, "race_number", 0) == race_number]
        if not matches:
            print(_j.dumps({"renamed": False, "reason": "not found"}))
            return {"renamed": False}
        # Rename the LAST match (the first is reachable; later ones shadow).
        target = matches[-1] if len(matches) > 1 else matches[0]
        target.bet_id = new_bet_id
    data_volume.commit()
    print(_j.dumps({"renamed": True, "bet_id": new_bet_id,
                    "status": target.status}))
    return {"renamed": True}


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=256,
    timeout=300,
)
def settle_one(bet_id: str) -> dict:
    """Diagnose + settle a single open bet, printing the verdict path.
    Uses placedAt fallback for age so dateless fossils can't hide."""
    import os
    import sys
    import json as _j
    import asyncio as _a

    sys.path.insert(0, "/app")
    os.environ.setdefault("DATA_DIR", "/app/data")
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor
    from core_agent.skills.result_tracker import ResultTracker

    gov = BankrollGovernor(data_dir="/app/data")
    bet = next((b for b in gov._bets if b.bet_id == bet_id), None)
    if bet is None:
        print(_j.dumps({"bet_id": bet_id, "found": False}))
        return {"bet_id": bet_id, "found": False}
    print(_j.dumps({
        "bet_id": bet_id,
        "status": bet.status,
        "date": getattr(bet, "date", None),
        "has_notes_combos": "combinations" in str(getattr(bet, "notes", "")),
    }))
    tracker = ResultTracker(bankroll_governor=gov)
    try:
        from core_agent.skills.result_tracker import _parse_exotic_ticket
        ticket = _parse_exotic_ticket(bet)
        print(_j.dumps({
            "parsed_pool": (ticket or {}).get("pool_type"),
            "parsed_legs": (ticket or {}).get("pool_legs"),
            "parsed_combos": len((ticket or {}).get("combos", [])),
        }))
    except Exception as e:
        print(_j.dumps({"parse_error": str(e)[:200]}))
    data_volume.commit()
    return {"bet_id": bet_id, "status": bet.status}
