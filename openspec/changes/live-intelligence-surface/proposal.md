# Proposal: Live Intelligence — one signal stream, one punter-facing Live tab

## Why

Strike Tips now shows the same fact in four places, and none of them is the
right place.

A price moved. That fact surfaces as a **Logs** row (`ALERTENGINE ·
ODDS_DROP` — "King Lee @ Churchill Downs R7: Opportunity detected (Odds Drop
| Odds: 6)"), as a **Market Movers** card (with movement %, steamer flag and
direction colour), as a **Live Ops** telemetry line, and as a **Telegram**
digest row ("📉 STEAMER 🐎 Bright Comet @ Vaal R5 — 3.5 (04:55) → 2.87
(12:30)"). Each surface computes its own view of the event, from its own
source, on its own schedule. A punter choosing a runner on the dashboard does
not see that its runner is steaming; a punter on Telegram sees moves but
nothing about their own pick.

Two more problems sit underneath:

**The movers feed is stale and walled.** ATR's Market Movers page is the
primary source for every surface above. It is behind the same Fastly client
challenge that broke the results feed (a 3,038-byte "Client Challenge"
shell), and it refreshes on a **45-minute** gate
(`ATR_REFRESH_MIN_GAP_SECS = 45 * 60`). Our own market snapshot refreshes
every **5 minutes** and covers Betway *and* Betfair — fresher, multi-book,
and not behind a challenge wall. The Telegram digest's own rows prove the
lag: a move stamped 13:15 reaches the digest at 13:46.

**Nothing shows a race as it runs.** A race lasts 3–6 minutes. Our 5-minute
poll sees roughly one update per race, so the system can show the card and
the result but never the race. The market movers tab shows pre-race drift
hours before the off ("off 14:35, 129m"). There is no punter surface for
"this race is running right now, your pick is 3rd, the market just chased it".

## What changes

1. **Canonical market events.** One record shape, one store
   (`market_events.jsonl` on the data volume), one writer. Every surface
   filters the same records instead of deriving its own. The detector
   already exists — the alert engine's `ODDS_DROP` events are price moves
   with a race and a horse on them — so this is normalisation and
   persistence, not new detection.

2. **Our own movers.** Price moves computed by diffing consecutive market
   snapshots (5-minute cadence, all books), written to the canonical store
   and consumed by the Movers tab, the Live tab, the Logs audit and the
   Telegram digester. ATR's movers page stays as a **tagged fallback** for
   meetings we do not scrape — demoted from primary, with its age shown.

3. **A punter-facing `Live` tab.** One meeting, one race: live prices with
   movement, the AI read reacting to the move, **the user's own league pick
   in that race**, and a contextual "watch live" link. After the race: the
   result, the settlement, the points, the leaderboard move. This is the
   surface no bookmaker can copy — Betway has prices and video, only we know
   what the user's pick is doing while it runs.

4. **Nav cleanup, because the rename forces it.** `Live Ops` (agent engine
   telemetry + races × news) becomes **`Engine Ops`** and moves to the
   operator group. `Logs` stays `Logs` — it is an audit trail, the word
   operators rely on, and `/logs` is a shared URL. The "Live Races ⨯
   Stories" half of the old Live Ops moves into the new Live tab, where it
   has the race context it needs.

5. **A first-party analytics sink.** `promoEvent()` currently dispatches a
   DOM `CustomEvent` and logs to the console — the events go nowhere. They
   go to a first-party endpoint instead, so watch time and engagement are
   measurable. This is the number 2027's advertising and sponsor pricing
   will be judged on, and it is the only way to tell a pretty screen from a
   useful one.

## Impact

- **No new source.** Every part of this runs on data we already collect.
- **No rights question.** The "watch live" control is a plain link to the
  broadcaster's own page; nothing is embedded, proxied or re-streamed.
- **One optional spike.** Whether *in-play* prices are possible depends on
  holding Betway's `TrackRacing` SignalR hub open (the hub their own site
  uses). That is a ten-minute feasibility test, and it gates how live the
  Live tab can honestly be — it does not gate the rest of the change.
- **Dependency.** The Live tab's meeting switcher needs the Gulf region
  fix (UAE + Bahrain missing from the region maps), which is a separate,
  earlier change.
