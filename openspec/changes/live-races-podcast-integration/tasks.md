## Tasks: Live Races Deep Integration in Swarm Podcast

- [x] 1.1 In `strike-tips-hud/server/podcast-service.ts`, enrich `GeneratePodcastRequest` and the prompt builder with `distanceM`, `raceTime`, `complexity`, `dsi`, and rich runner attributes (`jockey`, `trainer`, `draw`, `gear`, `daysSinceRun`).
- [x] 1.2 In `strike-tips-hud/src/components/SwarmPodcastView.tsx`, implement a live race selector with rich race cards/options (course, race number, post time, distance, field size).
- [x] 1.3 Add a Live Race Intelligence Strip showing active race conditions, post time, and field overview.
- [x] 1.4 Wire the generate handler to bundle the exact selected live race's full state into the API request.
- [x] 1.5 Run `compile_applet` and verify end-to-end build integrity.
