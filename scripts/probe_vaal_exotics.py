"""Probe: today's Vaal BIPOT + PA tickets with full combinations."""
import json
import os
import urllib.request

key = os.environ["KEY"]
req = urllib.request.Request(
    "https://gmpho--strike-tips-racing-serve-api.modal.run/api/betting/open",
    headers={"x-api-key": key},
)
with urllib.request.urlopen(req, timeout=25) as r:
    data = json.load(r)

for b in data.get("bets", []):
    bid = str(b.get("id", ""))
    horse = str(b.get("horse", ""))
    if bid.startswith("20260922") and ("BIP" in bid or "PLA" in bid):
        print("ID:", bid)
        print("  ticket:", horse)
        print("  track:", b.get("track"), "| race:", b.get("raceNumber"),
              "| stake: R", b.get("stake"), "| status:", b.get("status"))
        try:
            n = json.loads(b.get("notes", "{}"))
            print("  legs:", n.get("pool_legs"))
            for c in n.get("combinations", []):
                print("   R%s: banker %s | savers %s"
                      % (c.get("race"), c.get("banker"), c.get("savers")))
        except Exception as e:
            print("  notes parse:", e)
