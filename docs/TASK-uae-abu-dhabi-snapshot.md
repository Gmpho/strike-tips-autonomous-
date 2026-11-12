# Task: UAE (Abu Dhabi) races missing from the live market snapshot

**Status:** open — to be picked up in the morning
**Raised:** 2026-11-12 (after the USA settlement / race-number session)

## Symptom

`strike-tips-hud.pages.dev/results` shows **Abu Dhabi (UAE)** — 3 races
(13:00 Yas Sprint Prep Stakes, 13:30 Wathba Stallions Cup, 14:00 Abu Dhabi
Derby Prep) with **full finishing orders** (13, 18 and 11 runners, every
position and SP). ATR's results feed covers UAE perfectly.

But the **live market snapshot** (`market_snapshot_latest.json`, the HUD's
live odds/cards) has **no UAE meeting at all** — so those races carry no
live odds, no AI selection and no market state. Betway's own site does
list Abu Dhabi.

## Root cause (confirmed by code inspection, 2026-11-12)

`core_agent/skills/parsers/betway_api.py` asks Betway for **South Africa
only**, and then filters the regions it gets back through a hard-coded
allowlist that has no Middle East:

```python
# line 38 — the feed itself is scoped to ZA
daily_url = (f"{self.BASE_URL}/GetDaily?sportId=horse-racing&period=Today"
             f"&isVirtual=false&countryCode=ZA&timeZoneOffset=2")

# lines 46-55 — and only these regions are kept
ALLOWED = [
    "South Africa", "UK and Ireland", "Australia", "New Zealand",
    "USA", "Hong Kong", "Japan", "France",
]
```

So a UAE meeting can never enter the snapshot from the Betway path, no
matter what Betway publishes.

## What to check (morning)

1. **Does Betway expose UAE under a different country code?**
   `https://www.betway.co.za/api/horse-racing/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=AE&timeZoneOffset=2`
   — and does dropping `countryCode` widen it? (the ZA feed may simply not
   carry UAE, in which case the country code is the only change needed.)
2. **Does the Betfair SA exchange feed already list it?**
   `core_agent/skills/parsers/betfair_sa.py` has `_COUNTRY_FILTER = None`
   (no filtering) and its host serves US/UK/SA — that is the path the US
   and UK meetings came in through. If it carries the UAE meeting, the
   UAE events only need the region mapping, not a new source.
3. **Region mapping:** does `core_agent/skills/league/regions.py` know
   "United Arab Emirates" / "Abu Dhabi"? An unmapped course is dropped by
   the region filters even when the feed delivers it.
4. **Does the ATR racecard page for UAE exist?** ATR results carry the full
   card, so the race-level data is already there — only the *live* odds
   side is missing.

## Definition of done

- The UAE meeting appears in `market_snapshot_latest.json` with live odds.
- The HUD's live card shows Abu Dhabi with prices (not SP placeholders).
- Settlement for UAE league picks resolves (ATR results already provide
  the full finishing order, so the confirmed-cards path should work).
- A regression test covers the region/allowlist change, so a new country
  is a one-line edit and not a hunt.
