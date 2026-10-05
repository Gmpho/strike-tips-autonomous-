# Region Unlock Playbook (Oct-2026)

Europe (UK/IRE) was the template. Every future region (USA, AUS, Hong Kong,
France, Japan…) unlocks through the same 5 steps, in order. No region skips
steps; no region shares another's evidence.

## Step 1 — Manifest coverage (data door)

- TAB manifest lists the region's meetings with dated PDFs (`tab_content.py`
  already parses any `MEETING(REGION)@date.pdf` shape — new regions usually
  work with zero code).
- Proof: 7 consecutive days with the region's cards present and parseable.
- If the manifest lacks the region: region stays LOCKED, full stop.

## Step 2 — OKF shelf (context door)

- `knowledge/racing/tracks-<region>/`: deep-dives for the region's
  actually-carded courses + full index of the rest (same pattern as
  tracks-uk/tracks-ie). Punter rules, draw biases, surfaces.
- Status tracked in `tracks-intl/index.md` (locked → shelf → live).
- Rebuild bundle, verify search ranks the new shelf.

## Step 3 — Feed context (ATR equivalent)

- Whatever the region's form/movers feed is (ATR for UK/IRE, equivalents
  elsewhere): meeting-aware parsing + course map entries + snapshot backfill.
- Proof: zero "Unknown Venue" cards for the region over a week.

## Step 4 — Wave + digest + alerts (live door)

- Modal cron per timezone wave (budget: 5 crons max, 4 used — Europe holds
  one; next region either takes the 5th slot or shares a multi-region cron).
- Digest in morning format → individual alerts (stake 0.00) → quality review.

## Step 5 — Stage-3 gates (money door)

- Same 5 gates as `STAGE3_UNLOCK.md`, evidence per region. SA/UK evidence
  never counts toward another region.

## Region status board

| Region | Manifest | OKF shelf | Feed | Wave | Stage |
|--------|----------|-----------|------|------|-------|
| SA | ✅ live | ✅ live | ✅ live | ✅ 05:00 | ✅ live money |
| UK/IRE | ✅ live | ✅ live | ✅ live | ✅ 12:30 | digest+alerts |
| France/Sweden | manifest lists | — | — | — | LOCKED |
| Hong Kong | manifest lists | — | — | — | LOCKED |
| Australia | manifest lists | — | — | — | LOCKED |
| USA/Japan | manifest lists | — | — | — | LOCKED |
