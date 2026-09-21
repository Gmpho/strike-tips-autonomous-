"""One-shot probe: open bets + recent history from the live API."""
import json
import urllib.request

BASE = "https://strike-tips-hud.pages.dev/api"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.load(r)


open_bets = get("/betting/open")
bets = open_bets.get("bets", open_bets if isinstance(open_bets, list) else [])
print("=== OPEN:", len(bets), "===")
for b in bets[:10]:
    print({k: b.get(k) for k in ("bet_id", "id", "horse", "race_number",
                                 "track", "stake", "odds", "status", "date", "bet_type")})

hist = get("/betting/history")
hbets = hist.get("bets", hist if isinstance(hist, list) else [])
print("=== HISTORY:", len(hbets), "===")
for b in hbets[-8:]:
    print(b.get("date"), str(b.get("horse", ""))[:34], b.get("bet_type", ""),
          "stake", b.get("stake"), "status", b.get("status"), "pl", b.get("profit_loss"))
