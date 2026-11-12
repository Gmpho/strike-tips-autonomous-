# Tasks: Live Intelligence

## 0. Spike — can we read in-play prices? (10 min, gates nothing but informs)

- [ ] 0.1 Open Betway's `TrackRacing` SignalR hub and read one price change
      (`https://sportsapi.betway.{tld}/synapse-hub`, hub id `TrackRacing`)
- [ ] 0.2 Record the verdict (works / blocked / needs auth) in the change
      folder; the Live tab ships either way

## 1. Nav cleanup

- [ ] 1.1 `Live Ops` → `Engine Ops` in the sidebar; keep the `telemetry`
      route id and `/telemetry` working; add `/engine-ops` alias
- [ ] 1.2 Keep `Logs` as `Logs`; `/logs` unchanged; add `/live` alias for the
      new tab
- [ ] 1.3 Move `Engine Ops` into the operator group beside Vitals / Healing
- [ ] 1.4 Move "Live Races × Stories" out of the engine view into the Live
      tab; engine view keeps engine telemetry only

## 2. Canonical market events

- [ ] 2.1 Define the event record and write `market_events.jsonl` on the data
      volume (atomic write, temp + `os.replace`)
- [ ] 2.2 Normalise the alert engine's `ODDS_DROP` events into canonical
      records (race id, course, race no, horse, from, to, delta %, severity,
      source, is_user_pick)
- [ ] 2.3 Join the user's league picks onto the events (`names_match`, the
      pick's `race_id` / `off_iso`)
- [ ] 2.4 Prune the store by age on the same TTL the other volume caches use
- [ ] 2.5 Serve the store through the API the HUD already polls

## 3. Our own movers (snapshot diffing)

- [ ] 3.1 Diff consecutive `market_snapshot_latest.json` per
      (course, race, runner); track a price per book
- [ ] 3.2 A move requires: same book, change above threshold, and not a
      placeholder→real transition
- [ ] 3.3 Per-race debounce so one busy race cannot flood the surfaces
- [ ] 3.4 Write our movers as canonical events; demote ATR's movers to a
      tagged fallback with its age
- [ ] 3.5 Point the Movers tab, the Logs audit and the Telegram digester at
      the canonical store; remove their private derivations
- [ ] 3.6 Show source + age on every movers entry

## 4. The Live tab

- [ ] 4.1 New route `live`; meeting switcher driven by the region map
- [ ] 4.2 Live race header: race no, off time, elapsed clock, next off
- [ ] 4.3 Runners with price, movement direction/size/% and the steamer flag
      (reuse `MovementBadge`, `parseMovement`, `isSteamer`)
- [ ] 4.4 "Your pick" strip: the user's league pick in that race, its price
      and the movement in it
- [ ] 4.5 AI in-play read that reacts to the movement (including "the market
      chased it — our edge is fading")
- [ ] 4.6 After the race: result, settlement, points, leaderboard movement
- [ ] 4.7 Data-age indicator; never render "live" on stale prices
- [ ] 4.8 Watch-live control on the live race only; plain link out, no
      embed; tab stays usable if the broadcaster page is unavailable
- [ ] 4.9 "Live Races × Stories" block lands here
- [ ] 4.10 Promo / sponsor slot in the Live tab

## 5. Analytics sink

- [ ] 5.1 `promoEvent` posts to a first-party endpoint (Worker → D1 /
      Analytics Engine); no third-party tracker, no cookie banner
- [ ] 5.2 Record: page_view, live_tab_open, race_followed,
      race_card_viewed, watch_live_click, promo_impression / cta / dismiss
- [ ] 5.3 Derive per-surface time-on-surface and races followed

## 6. Tests

- [ ] 6.1 Canonical event written once and read identically by every surface
- [ ] 6.2 Placeholder→real price is not a move; same-book rule holds
- [ ] 6.3 Per-race debounce collapses repeats
- [ ] 6.4 ATR-sourced events carry the source tag and age
- [ ] 6.5 A stale race renders without a live badge
- [ ] 6.6 The watch-live control appears only on the live race and links out
- [ ] 6.7 `/logs`, `/telemetry` still resolve; `/engine-ops`, `/live` resolve
- [ ] 6.8 The user's pick is joined to its event and shown on the Live tab
- [ ] 6.9 Analytics events are recorded with no third-party request

## 7. Ship

- [ ] 7.1 Full suite green in docker (host runs lack fastapi), commit, push
- [ ] 7.2 Deploy on the user's approval
- [ ] 7.3 Write the report of what the Live tab changed for the user
      (and update `openspec/specs/` on archive)

## Dependencies

- 4.1's meeting switcher needs the **Gulf region fix** (UAE + Bahrain in
  both region maps) — a separate, earlier change.
- 4.4 and 4.5 need §2 (canonical events with the pick join).
- 4.3 needs §3 (our own movers) or falls back to ATR movers with its age.
