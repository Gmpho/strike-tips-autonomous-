## Context

See proposal.md (Why) and the two spec files (behaviour contracts).

Current state shaping the approach:

- The **market snapshot** (`market_snapshot_latest.json`) refreshes every
  5 minutes on the odds-monitor cron and holds Betway + Betfair prices for
  every meeting in the card (43 events on 2026-11-12: Churchill Downs 9,
  Mahoning Valley 8, Belmont Park 8, Horseshoe Indianapolis 7, Woodbine 4,
  plus the UK/IRE meetings).
- **ATR's Market Movers page** (`atr_movers_snapshot.json`) is the current
  source for every "a price moved" surface. It refreshes on a 45-minute gate
  and sits behind the Fastly client challenge — the same wall that took the
  results feed down on 2026-11-12.
- The **alert engine** already emits per-race odds-drop events
  (`ALERTENGINE · action: ODDS_DROP`) and they are visible in the HUD's
  Logs view under "ALERTS TRIGGERED".
- The HUD already has a **Market Movers** view with `parseMovement`,
  `isSteamer` and `MovementBadge` components, fed by an SSE
  `market-movers` event.
- The HUD's **Live Ops** view is two things: agent engine telemetry (SSE)
  and a "Live Races × Stories" block.
- The HUD's **Logs** view ("Telemetry & Logs — Operations Audit Trail") has
  the tabs All operations / Betting logs / Alerts triggered / Sync & healing.
- `promoEvent()` in `strike-tips-hud/src/lib/campaigns.ts` dispatches a DOM
  `CustomEvent` and a console log. Nothing consumes or forwards it.
- Betway's own site opens a SignalR hub at
  `https://sportsapi.betway.{tld}/synapse-hub` with hub id `TrackRacing`,
  scoped to racing pages, and connects/stops it on navigation. Their
  betting interface uses it for live price pushes.

## Goals / Non-Goals

**Goals:**

- One canonical record for "something happened in a market", written once
  and read by every surface — so the four surfaces can never disagree.
- Price moves computed from our own 5-minute snapshot (all books), with
  ATR's movers demoted to a tagged, age-labelled fallback.
- A punter-facing `Live` tab: live race, movement, the user's own pick, the
  AI read reacting to the move, the result and settlement afterwards.
- A punter-facing "watch live" control that appears only on the race that
  is actually live, and links out — no embedding, no partner agreement
  needed for it to work.
- Navigation that names things once: `Engine Ops` (agent telemetry),
  `Logs` (audit trail), `Live` (races in play).
- Measurable engagement: a first-party sink for the events we already
  fire, and a watch-time number.

**Non-Goals:**

- Embedding, proxying or re-streaming any broadcast picture. The control
  is a link to the rights holder's own page. Licensing picture ourselves is
  a separate business decision.
- Taking bets, holding a gaming licence, or becoming a bookmaker. We stay
  intelligence; money moves only on paper.
- Advertising networks and affiliate revenue (both need a registered domain
  and a partner agreement — 2027 work).
- Replacing the Telegram digests. They stay; they become one consumer of the
  canonical events rather than the only one.
- Predictor, Dreaming, Swarm, Exotics, Bankroll, Analytics, Results,
  Leaderboard, Picks: unchanged.

## Decisions

**One event store on the data volume, not a new table.**
`market_events.jsonl` beside `league_picks.jsonl` and
`confirmed_results.jsonl`, written atomically (temp file + `os.replace`),
read by the API which already serves the HUD. Rationale: the volume is
where every other race-side artefact already lives, the writer is a
cron-driven single process, and there is no query-by-join requirement that
would justify a database. Alternative (Supabase table) rejected: no
concurrent writers, no ad-hoc querying, and the league data already lives
on the volume.

**Our own movers by snapshot diffing, not by scraping a third page.**
Consecutive snapshots are diffed per (course, race, runner); a move is
recorded when a runner's price changes by more than a threshold. Rationale:
5 minutes instead of 45, two books instead of one, and no dependence on a
page that is currently challenge-walled. Alternative (keep ATR as primary)
rejected: the digest rows already show the lag, and ATR's feed was
unavailable for most of 2026-11-12.

**Cross-book flicker is handled by comparing like-for-like.**
A runner's price is tracked per book; a "move" is a change within one
book, and the displayed price is the best available across books. SP → a
real price is not a move (it is a market opening). A minimum percentage
and a per-race debounce keep noise out — the digest already suppresses by
per-race cooldown and the same rule applies here.

**The Live tab is a new route, not a re-skin of Live Ops.**
`Live Ops` is renamed `Engine Ops` and keeps only engine telemetry; the
"Live Races × Stories" block moves to the new tab, where the race context
it needs exists. Rationale: an operator tool and a punter surface have
different audiences, different density and different refresh needs, and
mixing them is why the old view felt like neither.

**Labels change; ids and paths do not.**
The nav entry keeps its route id (`telemetry`) and `/logs` and `/telemetry`
keep resolving; aliases `/engine-ops` and `/live` are added. Rationale:
`/logs` is a shared URL and operators bookmark it; a rename that breaks a
shared link is a bad trade for a better word.

**"Live" is a claim the data must support.**
The Live tab shows the age of the data it is rendering, and never labels a
race live on prices it knows are stale. Rationale: the system's hardest-won
property this season was never asserting a result it could not prove; the
same discipline applies to liveness.

**Your pick is the centrepiece, not an extra.**
The Live tab joins the canonical events to the user's league picks. The
join already exists in the settlement code (`names_match`, and the pick's
`race_id`/`off_iso`). Rationale: this is the one thing a bookmaker cannot
copy, and it is what turns a price feed into intelligence.

**Analytics goes to a first-party endpoint.**
`promoEvent` posts to a Worker route backed by D1 (or Analytics Engine),
not to a third-party tracker. Rationale: no cookie-consent surface, no
third-party policy risk, and the data stays ours. A first-party beacon is
also what makes watch time measurable without a consent banner.

**SignalR is a spike, not a dependency.**
Whether *in-play* prices are obtainable is tested separately (open the
`TrackRacing` hub, read one price change). The Live tab ships either way:
with in-play prices if the spike succeeds, otherwise on 5-minute snapshot
diffs — which is still far better than today's pre-race-only movers.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Snapshot diffing produces false moves (book switches, SP→price, partial prices) | per-book tracking, minimum % threshold, per-race debounce, SP handled explicitly |
| The canonical store grows without bound | prune by age (the volume already prunes `atr_full_results_cache.json` and `settled_winners.jsonl` on a TTL) |
| The Live tab claims liveness it does not have | render the data age; "live" only when the last price is inside the poll window |
| Two movers sources disagree (ours vs ATR) | one primary (ours); ATR tagged `source: atr` with its age; surfaces show the source on hover |
| The HUD's region map and the backend's drift apart again (UAE/Bahrain) | the Live tab's meeting switcher reads one map; a test asserts both maps agree on the regions they share |
| Clicking out to a broadcaster costs us the session | the button is one per live race, never a row of them, and the Live tab's own value (your pick, the AI read, the result) is what brings them back |

## Wrap-up

After this change: one signal stream, one Live tab, honest freshness
labels, and a measured watch time — with no new source, no rights question
and no partner dependency.
