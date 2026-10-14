## Why

South African racing broadcasts (e.g. Racing 240 / Hollywoodbets Durbanville / TOTE) feature a popular 20-30 second animated race predictor visualizer before races. Punters and bettors love seeing visual representation of race outcomes rather than static tables of numbers. Strike Tips currently presents racecards in tables, missing this visual excitement. Furthermore, broadcast predictors are strictly deterministic (often only showing the heavy favourite winning), whereas Strike Tips specializes in probabilistic edge analysis. Adding a 20-30s interactive race simulation with dual modes (Deterministic Expected vs. Monte Carlo Reality) in a dedicated panoramic sidebar view engages users and vividly demonstrates why value betting on outsiders works without cluttering dashboard racecards.

## What Changes

- Add a client-side pacing and margin calculation engine (`pacingEngine.ts`) calculating 3-phase race trajectories, barrier draw positioning, and finish margins.
- Add an HTML5 60 FPS Canvas race track visualizer (`RaceTrackCanvas.tsx`) depicting a turf track, rail banners, distance markers, galloping animated sprites, saddlecloth numbers, and silks.
- Add a dedicated full-page sidebar view (`RaceSimulatorView.tsx`) under Racing Intelligence with racecard selector carousel, playback controls (play/pause, reset, speed toggle, mode toggle, and value-bet spotlight), and live finish margin leaderboard.
- Add a "⚡ Simulate Race" trigger button to `RaceCard.tsx` on the dashboard that redirects directly to `/simulator` with that race pre-selected.
- Support both Expected (Consensus) mode and Monte Carlo (Stochastic) mode, proving how outsiders like Secret Tactic win when front-runners burn out.

## Capabilities

### New Capabilities
- `race-simulator-visualizer`: Interactive 20-30s race predictor visualizer and pacing simulation engine with dedicated sidebar page and card redirection in the HUD.

### Modified Capabilities
<!-- None -->

## Impact

- `strike-tips-hud/src/components/RaceCard.tsx`: Adds simulation redirect button.
- `strike-tips-hud/src/components/sidebar/RaceSimulatorView.tsx`: New dedicated full-screen simulator view.
- `strike-tips-hud/src/components/sidebar/Sidebar.tsx`: Adds "Race Simulator" navigation item.
- `strike-tips-hud/src/engine/simulation/`: New physics and pacing math engine.
- Zero server backend overhead, zero database changes, zero extra dependencies added.
