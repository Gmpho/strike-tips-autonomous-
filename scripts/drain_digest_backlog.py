"""Drain stale digest backlog (Sep-2026 spam storm cleanup, one-off).

Removes queue entries older than 1h (the repeated UK-track storm), keeps
fresh ones. Run: modal run scripts/drain_digest_backlog.py::drain
"""
import modal

app = modal.App("digest-backlog-drain")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .add_local_file(
        "core_agent/config/paths.py",
        "/app/core_agent/config/paths.py",
    )
)
vol = modal.Volume.from_name("strike-tips-data", create_if_missing=False)


@app.function(image=image, volumes={"/app/data": vol}, timeout=120)
def drain() -> dict:
    import json
    import os
    import sys
    import time

    sys.path.insert(0, "/app")
    from core_agent.config.paths import DATA_DIR

    out: dict = {}
    for name in ("alert_digest_queue.jsonl",):
        path = str(DATA_DIR / name)
        kept, dropped = [], 0
        try:
            with open(path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            out[name] = "missing"
            continue
        cutoff = time.time() - 3600
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                dropped += 1
                continue
            try:
                ts = float(rec.get("ts") or 0)
            except Exception:
                ts = 0
            if ts and ts < cutoff:
                dropped += 1
            else:
                kept.append(line)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(("\n".join(kept) + "\n") if kept else "")
        os.replace(tmp, path)
        out[name] = {"kept": len(kept), "dropped": dropped}
    return out
