# Task: UAE + Bahrain races missing from the live market snapshot

**Status:** open — to be picked up in the morning
**Raised:** 2026-11-12 (after the USA settlement / race-number session)

**Scope widened:** Bahrain is also racing from tomorrow (2026-11-13), so this
covers the **Gulf block** — UAE (Abu Dhabi, Meydan, Jebel Ali) and Bahrain
(Bahrain International / Sakhir). Both share the same Nov→Apr season, so
both are invisible today and both need the same three fixes.

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

### Filter 1 — Betway is scoped to South Africa, and its allowlist has no Middle East

`core_agent/skills/parsers/betway_api.py` asks Betway for **South Africa
only**, then filters the regions it gets back through a hard-coded
allowlist:

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

### Filter 2 — the backend's region map has no UAE and no Bahrain

`core_agent/skills/league/regions.py` resolves a course to a region from
**hard-coded track lists** (`_SA`, `_UK_IE`, `_HK`, `_JP`, `_AUS`, `_USA`,
`_CAN`). There is **no UAE and no Bahrain entry**, so
`region_of("Abu Dhabi (UAE)")` and `region_of("Bahrain International")`
both return `"OTHER"` — and the file's own docstring says it "mirrors
strike-tips-hud/src/lib/regions.ts", which knows **UAE** but **not
Bahrain**:

```ts
// strike-tips-hud/src/lib/regions.ts
UAE: { code: 'UAE', label: 'UAE', flag: '🇦🇪' },
meydan: 'UAE', 'jebel ali': 'UAE',
[/\buae\b|dubai|emirates/, 'UAE'],
// no Bahrain, no Sakhir
```

So the two maps have drifted apart, and neither covers Bahrain: the HUD
can label a UAE race, the backend routes it to `"OTHER"`, and a Bahrain
race is `"OTHER"` in both. The same drift already bit once (the UK list
carries the note *"Nov-2026: TAB serves these weekly but they were
missing, so their tickets resolved to 'OTHER' and the HUD's jurisdiction
filter hid them"*).

### Ruled out — there is no year or season filter

Checked 2026-11-12: no `season`, month-range or year filter exists on the
live path. The odds monitor only ever asks for **today / yesterday /
tomorrow** (`adaptive_odds_monitor.py` builds date candidates around
`now`), never a year window. The only "season" strings in the repo are UI
text and knowledge-base prose. So a Dubai Nov→Mar season cannot be what
excludes it — the exclusions are the two static allowlists above.

(That said, the *season* is still worth keeping in mind as the **reason
this never showed up**: UAE racing only runs roughly Nov→Mar, so in
May→October the meeting simply does not exist and nothing looks wrong.
The gap only becomes visible now that the season has started.)

## What to check (morning)

1. **Does Betway expose the Gulf under a different country code?**
   `https://www.betway.co.za/api/horse-racing/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=AE&timeZoneOffset=2`
   — and `countryCode=BH` for Bahrain? And does dropping `countryCode`
   widen it to both? (the ZA feed may simply not carry them, in which case
   the country code is the only change needed.)
2. **Does the Betfair SA exchange feed already list them?**
   `core_agent/skills/parsers/betfair_sa.py` has `_COUNTRY_FILTER = None`
   (no filtering) and its host serves US/UK/SA — that is the path the US
   and UK meetings came in through. If it carries the Gulf meetings, those
   events only need the region mapping, not a new source.
3. **Region maps — both sides:**
   - `core_agent/skills/league/regions.py`: add a Gulf region with
     `abu dhabi`, `meydan`, `jebel ali`, `bahrain`, `sakhir`;
   - `strike-tips-hud/src/lib/regions.ts`: add the missing **Bahrain**
     region (UAE is already there) plus its flag and track mappings.
   Keep the two files in step — the backend's docstring claims they
   mirror each other, and they have drifted.
4. **Results coverage:** ATR's results page already carries UAE (proven —
   full cards on /results). Confirm **Bahrain** is there too, so the
   settlement path has full finishing orders for both.
5. **Offtrackbetting's course index** (`otb_courses.json`, ~1,034 entries
   on the data volume): does it carry **Abu Dhabi** and **Bahrain**? If so,
   the confirmed-cards path can settle Gulf league picks even before ATR
   enrichment recovers.

## Definition of done

- The UAE **and** Bahrain meetings appear in `market_snapshot_latest.json`
  with live odds.
- The HUD's live card shows both, with prices (not SP placeholders) and a
  correct region label in both maps.
- Settlement for Gulf league picks resolves (ATR results, or OTB cards if
  its index carries them).
- A regression test covers the region/allowlist change, so a new country
  is a one-line edit and not a hunt.
