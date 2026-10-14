## 1. Engine & Math Setup

- [x] 1.1 Implement pacing and margin calculation engine in `strike-tips-hud/src/engine/simulation/pacingEngine.ts` and verify trajectory math.

## 2. Visualizer Canvas Component

- [x] 2.1 Implement 60 FPS HTML5 Canvas racetrack and horse sprite renderer in `strike-tips-hud/src/components/simulator/RaceTrackCanvas.tsx`.

## 3. Dedicated Sidebar View & Controls

- [x] 3.1 Implement `RaceSimulatorView.tsx` with racecard selector carousel, dual mode toggles, play/pause controls, reset, and live margin leaderboard.
- [x] 3.2 Add "Race Simulator" navigation entry to `strike-tips-hud/src/components/sidebar/Sidebar.tsx` and register route in `App.tsx`.

## 4. HUD Integration & Build Verification

- [x] 4.1 Connect "⚡ Simulate Race" trigger on `strike-tips-hud/src/components/RaceCard.tsx` to redirect cleanly to `/simulator`.
- [x] 4.2 Run `npm run build` in `strike-tips-hud` and verify clean TypeScript compilation and bundle generation.
