"""Probe: check TAB dividend availability for today's Vaal and the scraper URL set."""
import urllib.request
import json
import datetime

today_iso = datetime.date.today().isoformat()
print("today:", today_iso)

urls = [
    ("tab4racing-today", f"https://www.tab4racing.com/results/{today_iso}"),
    ("tab-today", f"https://www.tab.co.za/tabs/horse/all/{today_iso}/XVA"),
    ("racingvitesse", "https://www.racingvitesse.co.za/results?track=XVA&date=" + today_iso),
    ("raceform", "https://raceform.co.za/cards-results"),
]

for name, url in urls:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
        up = body.upper()
        print(name, "-> HTTP", r.status, "len", len(body),
              "| has BIPOT:", ("BIPOT" in up or "BI POT" in up),
              "| has PAYS:", ("PAYS" in up),
              "| has VAAL:", ("VAAL" in up))
    except Exception as e:
        print(name, "-> ERROR:", type(e).__name__, str(e)[:100])
