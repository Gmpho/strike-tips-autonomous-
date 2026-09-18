# Capability: Autonomous Swarm Racing Podcast

Specifies the autonomous multi-agent racing podcast system replacing generic voice synthesis.

## Requirements

### R1: Multi-Agent Swarm Cast
The system MUST provide a specialized 4-agent racing cast:
1. **Lead Paddock Presenter** (Sipho Ndlovu / Gemini Voice Kore) - Moderates discussion, frames prices, anchors coverage.
2. **Senior Form & Speed Analyst** (Gareth Vance / Gemini Voice Charon) - Analyzes track sectionals, turn of foot, course geometry, and jockey strike rates.
3. **Bayesian Edge & Kelly Modeler** (Dr. Elena Becker / Gemini Voice Zephyr) - Computes implied vs model win probabilities, edge percentages, and half-Kelly staking constraints.
4. **Trackside Scout & Going Reporter** (Tebogo Molefe / Gemini Voice Puck) - Assesses live going conditions, paddock demeanor, and rail bias.

### R2: Dynamic Script Generation
- The backend MUST expose `POST /api/podcast/generate` accepting `track`, `raceNumber`, and `runners` payload.
- The generation engine MUST analyze real contenders and yield structured JSON containing episode title, headline, summary points, and dialogue turns mapped to the 4 specialist roles.

### R3: Per-Turn Voice Audio Synthesis
- The backend MUST expose `POST /api/podcast/synthesize-line` to synthesize individual dialogue turns using Gemini TTS (`gemini-3.1-flash-tts-preview`) with assigned character voices.
- Audio MUST be encoded into standard PCM/WAV format for seamless browser playback.

### R4: Interactive HUD Player Experience
- The frontend MUST provide `SwarmPodcastView` featuring:
  - Master episode audio player with play/pause/skip/restart controls.
  - Synchronized speaker avatar, role badge, and dynamic audio wave indicator.
  - Interactive clickable transcript allowing instant jump to any speaker turn.
  - Race and track switcher pulling from live HUD race feeds.
