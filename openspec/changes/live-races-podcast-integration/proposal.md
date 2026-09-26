# Change: Live Races Deep Integration in Swarm Podcast

## Why
Previously, the Swarm Podcast only accepted a high-level course name (`Kenilworth`, `Greyville`, etc.) and defaulted to a generic Race 7. Punters could not select specific individual races on today's card (e.g., Race 1, Race 3, or the Pick 6 opener). Critical racecard dimensions (distance in metres, post time, draw stalls, jockey/trainer, gear tokens, days since run, and Dream Stress Index DSI) were not being forwarded to the AI scriptwriters.

## What Changes
1. **Podcast Service Request Payload (`podcast-service.ts`)**:
   - Extend `GeneratePodcastRequest` to accept `distanceM`, `raceTime`, `complexity`, `dsi`, and detailed runner form (`jockey`, `trainer`, `draw`, `gear`, `daysSinceRun`).
   - Format rich, ground-truth trackside context for the 5 Swarm agents so they debate actual live sprint/route distances, draw biases, and jockey strike rates.
2. **HUD Podcast Selector UI (`SwarmPodcastView.tsx`)**:
   - Replace generic course dropdown with an **Exact Live Race Selector** displaying Course, Race Number, Post Time, Distance, and Runner count.
   - Display a **Live Race Context Strip** highlighting the active race conditions, runner count, and top edge.
   - Forward all live race parameters directly to `/api/podcast/generate`.
