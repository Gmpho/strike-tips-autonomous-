## Context

ATR pages sit behind Fastly bot mitigation that alternates between serving
full pages and JS proof-of-work shells depending on client fingerprint, IP
reputation, and request rate. Modal egress IPs and the 5-min cron (4 pages ×
up to 3 tiers each ≈ 1150 fetches/day) proved enough to trigger day-long
penalty boxes. The monitor must keep Betway/Betfair sync on a tight loop
while treating ATR as slow-moving content.

## Goals / Non-Goals

**Goals:**
- ATR fresh within ~1h under normal conditions, honest staleness otherwise.
- Zero silent failures: every total loss is WARNING-visible with file ages.
- Browser solves available but rare (cost, time, flag-risk).

**Non-Goals:**
- Defeating bot mitigation aggressively (no rotating proxies, no solver arms
  race — polite cadence instead).
- Real-time ATR (content updates a few times daily; 45-min granularity is
  more than sufficient).

## Decisions

- **Packaging over cleverness**: the deepest outage came from a missing
  `patchright` wheel, not from ATR. Pin it everywhere and pre-download both
  Chromium flavors at build/boot.
- **Content markers over vendor markers**: discriminate shells by size and
  presence of the content the parser actually needs.
- **Cheap-first + throttle**: httpx/Fetcher succeed whenever the IP is in
  good standing (seconds, no flag risk); the browser only spends reputation
  when cheap tiers demonstrably fail, at most hourly.
- **Per-file cadence**: decouples feed recovery (one blocked feed must not
  force re-fetching healthy ones) and cuts steady-state volume ~10×.
- **Budget honesty**: 150s per ATR call and a 900s cron ceiling, sized from
  observed cold-Chromium solve times (40–60s+).

## Risks / Trade-offs

- A hard,Targeted IP block still starves ATR until reputation recovers; the
  system degrades to last-good + explicit staleness (accepted).
- 45-min granularity means breaking mover flashes can lag; acceptable for
  content that updates a few times daily.
- Browser profile persists on the volume (cookies survive); a poisoned
  profile could in theory stick — mitigated by throttle expiry and fresh
  cheap-tier attempts each cycle.
