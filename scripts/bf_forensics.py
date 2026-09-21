import modal
import time
import os
import glob
import json

app = modal.App("bf-forensics")
vol = modal.Volume.from_name("strike-tips-data", create_if_missing=False)
image = modal.Image.debian_slim(python_version="3.11")


@app.function(image=image, volumes={"/data": vol}, timeout=120)
def dump():
    out = {"files": []}
    for p in sorted(glob.glob("/data/betfair*")):
        out["files"].append({"name": os.path.basename(p), "size": os.path.getsize(p),
                             "mtime": os.path.getmtime(p)})
    for p, n in [("/data/healing_events.json", "healing"),
                 ("/data/market_snapshot_latest.json", "snap")]:
        try:
            with open(p) as f:
                out[n] = {"size": os.path.getsize(p), "mtime": os.path.getmtime(p),
                          "data": json.load(f)}
        except Exception as e:
            out[n] = {"error": repr(e)}
    return out


@app.local_entrypoint()
def main():
    r = dump.remote()
    now = time.time()
    print("== betfair* files on volume:")
    for f in r.get("files", []):
        print(f"   {f['name']}  size={f['size']}  age_min={(now - f['mtime']) / 60:.1f}")

    h = r.get("healing", {})
    hd = h.get("data") if isinstance(h, dict) else None
    if isinstance(hd, list):
        print(f"== healing: {len(hd)} events, last 15:")
        for e in hd[-15:]:
            print(f"   {e.get('timestamp')} {e.get('action')} {e.get('status')} {(e.get('details') or '')[:130]}")
    else:
        print("== healing:", h.get("error") or h)

    s = r.get("snap", {})
    sd = s.get("data") if isinstance(s, dict) else None
    if isinstance(sd, dict):
        ev = sd.get("events", {})
        bf = sum(1 for e in ev.values() if isinstance(e, dict) and (
            "bf_off_time" in e or any(isinstance(rr, dict) and ("gear" in rr or "daysSinceRun" in rr)
                                      for rr in (e.get("runners") or []))))
        print(f"== file snap: ts={sd.get('timestamp')} source={sd.get('snapshot_source')} "
              f"events={len(ev)} with_bf={bf}")
        print(f"   file mtime age_min={(now - s.get('mtime', 0)) / 60:.1f}")
    else:
        print("== snap:", s.get("error") or s)
