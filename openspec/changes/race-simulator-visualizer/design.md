## Context

See `proposal.md` for motivation. The Strike Tips HUD is built with React 19, Vite, Tailwind CSS 4, and Framer Motion. Race data is stored in `market_snapshot_latest.json` and populated with NHRA Merit Ratings, draw numbers, decimal odds, and win probabilities. We need a 60 FPS visual rendering engine that translates these metrics into an engaging 20-30 second broadcast-style race replay with zero server cost and zero added npm dependencies.

## Goals / Non-Goals

**Goals:**
- Provide a smooth 60 FPS HTML5 Canvas visualizer rendering a green turf track, rails, finish line, and animated galloping horses.
- Support dual simulation: Deterministic Expected mode (favourite leads) and Monte Carlo mode (outsiders can win).
- Provide a dedicated, panoramic sidebar view (`RaceSimulatorView.tsx`) to avoid crowding dashboard cards.
- Seamless redirection from dashboard `RaceCard.tsx` directly to the simulation view.
- Standalone pacing engine that accurately maps length margins (1 length $\approx$ 0.17s) to visual finish line arrival times.

**Non-Goals:**
- Embedding cramped modal overlays inside dashboard cards that cause container clipping and visual crowding.
- Heavy 3D mesh rendering or GPU-intensive WebGL shaders that might overheat low-end mobile devices.
- Video exporting/server-side MP4 generation.

## Decisions

### Decision 1: Dedicated sidebar view (`/simulator`) over in-card modal
- **Rationale**: Rendering simulation canvases inside narrow dashboard cards (e.g., 3-column grid) causes container clipping, layout crowding, and redundant DOM instances. A dedicated full-page view (`RaceSimulatorView.tsx`) gives the track full panoramic width, responsive controls, and a clean race selector strip.
- **Alternative considered**: In-card modal dialog. Rejected due to container transform clipping and cluttered dashboard UX.

### Decision 2: Canvas 2D over Three.js for core race replay
- **Rationale**: While Three.js is present in the bundle, Canvas 2D delivers guaranteed 60fps on mobile without WebGPU context loss or high power draw. It replicates the classic 2D broadcast look (seen on Racing 240 / LuckyFish) perfectly.
- **Alternative considered**: Full 3D track with Three.js. Rejected for initial version due to potential mobile GPU resets and heavier asset loading.

### Decision 3: Pure mathematical pacing engine (`pacingEngine.ts`)
- **Rationale**: Isolating margin and coordinate calculations into a pure module allows unit testing without DOM dependencies and enables future reuse (e.g. Monte Carlo backtesting).
- **Alternative considered**: Coupling physics logic directly inside React components. Rejected due to maintainability and testability concerns.

## Risks / Trade-offs

- [Risk]: User navigating between dashboard and simulator loses scroll position.
  → Mitigation: Standard URL route `/simulator` with browser history pushState and smooth scroll restoration.
