# Tasks: Live Intelligence

## 0. Spike — can we read in-play prices? (10 min, gates nothing but informs)

- [ ] 0.1 Open Betway's `TrackRacing` SignalR hub and read one price change
      (`https://sportsapi.betway.{tld}/synapse-hub`, hub id `TrackRacing`)
- [ ] 0.2 Record the verdict (works / blocked / needs auth) in the change
      folder; the Live tab ships either way

## 1. Nav cleanup

- [x] 1.1 `Live Ops` → `Engine Ops` in the sidebar; keep the `telemetry`
      route id and `/telemetry` working; add `/engine-ops` alias
      (alias map lives in `src/lib/routes.ts`, tested)
- [ ] 1.2 Keep `Logs` as `Logs` — **done for the "Logs stays" half**;
      `/logs` unchanged. The `/live` alias lands with the Live tab (§4).
- [x] 1.3 Move `Engine Ops` into the operator group beside Vitals / Healing
      (group heading renamed `Admin` → `Operator`, which is what the design
      called it)
- [ ] 1.4 Move "Live Races × Stories" out of the engine view into the Live
      tab — **blocked on §4.9**; it cannot move to a tab that does not exist
      yet, and leaving it homeless would be worse than leaving it in place

## 2. Canonical market events

- [x] 2.1 Define the event record and write `market_events.jsonl` on the data
      volume (atomic write, temp + `os.replace`)
      (`core_agent/core/market_events.py`; record carries id, ts, kind, race
      id/course/race no, runner name+number, prev, price, move %, severity,
      source, book, is_user_pick)
- [x] 2.2 Normalise the alert engine's `ODDS_DROP` events into canonical
      records (race id, course, race no, horse, from, to, delta %, severity,
      source, is_user_pick)
      (`record_alert()` called from the monitor's `_on_alert`, before any
      delivery gate so the audit trail does not depend on Telegram)
- [x] 2.3 Join the user's league picks onto the events (`names_match`, the
      pick's `race_id` / `off_iso`)
      (`load_pick_index` + `_pick_for`, fuzzy on the horse name, date-scoped)
- [x] 2.4 Prune the store by age on the same TTL the other volume caches use
      (26h — a full race day plus slack; pruned on every write)
- [x] 2.5 Serve the store through the API the HUD already polls
      (`/api/monitoring/snapshot` → `alerts` + `movers`)

## 3. Our own movers (snapshot diffing)

- [x] 3.1 Diff consecutive `market_snapshot_latest.json` per
      (course, race, runner); track a price per book
      (`diff_snapshot()`, hooked into `write_market_snapshot` so every
      producer of a snapshot feeds the stream)
- [x] 3.2 A move requires: same book, change above threshold, and not a
      placeholder→real transition
      (`is_move` + `real_price`; threshold mirrors the alert engine)
- [x] 3.3 Per-race debounce so one busy race cannot flood the surfaces
      (per-runner 10-min cooldown + 3 events per race per poll, keeping the
      biggest)
- [x] 3.4 Write our movers as canonical events; demote ATR's movers to a
      tagged fallback with its age
      (`from_atr` sets `source: "atr"` + `age_secs`; ATR rows for meetings
      we cover ourselves are dropped entirely)
- [ ] 3.5 Point the Movers tab, the Logs audit and the Telegram digester at
      the canonical store; remove their private derivations
      — **partial**: Movers tab ✅ and Logs ✅ (both via the snapshot
      endpoint). The Telegram digester still reads `odds_journey.json`;
      migrating it without breaking the digest's own journey rows is its own
      change, and its rows are correct today, only not canonical.
- [x] 3.6 Show source + age on every movers entry
      (`ProvenanceChip` in `MarketMoversView`; `age_secs` on every record,
      and the footer no longer claims the ATR feed is the source)

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

- [x] 6.1 Canonical event written once and read identically by every surface
      (`test_the_same_transition_cannot_be_stored_twice`; Movers and Logs
      both read the one store in `test_atr_cannot_outrank_a_course_we_scrape`
      / `test_an_alert_is_normalised_into_the_store`)
- [x] 6.2 Placeholder→real price is not a move; same-book rule holds
      (parameterised over `SP/0/1/None/n/a/""`, real→SP, and
      `test_a_book_switch_is_not_a_move`)
- [x] 6.3 Per-race debounce collapses repeats
      (cooldown honoured and expired, one event per poll, race capped at 3
      keeping the biggest)
- [x] 6.4 ATR-sourced events carry the source tag and age
      (`test_atr_events_carry_their_source_and_age`)
- [ ] 6.5 A stale race renders without a live badge — needs the Live tab
      (§4.7); the data needed (`age_secs`) is already on every record
- [ ] 6.6 The watch-live control appears only on the live race and links out
      — §4.8
- [x] 6.7 `/logs`, `/telemetry` still resolve; `/engine-ops` resolves
      (`tests/routes.test.ts`; `/live` lands with §4.1)
- [ ] 6.8 The user's pick is joined to its event and shown on the Live tab
      — **join done** (`test_the_event_knows_the_users_pick`); showing is
      §4.4
- [ ] 6.9 Analytics events are recorded with no third-party request — §5

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
