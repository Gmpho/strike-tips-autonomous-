# Capability: Autonomous Swarm Racing Podcast

## Purpose

Specifies the autonomous multi-agent racing podcast system replacing generic voice synthesis.

## Requirements

### Requirement: Multi-Agent Swarm Cast
The system MUST provide a specialized 4-agent racing cast:
1. **Lead Paddock Presenter** (Sipho Ndlovu / Gemini Voice Kore) - Moderates discussion, frames prices, anchors coverage.
2. **Senior Form & Speed Analyst** (Gareth Vance / Gemini Voice Charon) - Analyzes track sectionals, turn of foot, course geometry, and jockey strike rates.
3. **Bayesian Edge & Kelly Modeler** (Dr. Elena Becker / Gemini Voice Zephyr) - Computes implied vs model win probabilities, edge percentages, and half-Kelly staking constraints.
4. **Trackside Scout & Going Reporter** (Tebogo Molefe / Gemini Voice Puck) - Assesses live going conditions, paddock demeanor, and rail bias.

#### Scenario: Episode is cast with the four specialist roles
- **WHEN** an episode is generated
- **THEN** the cast SHALL consist of the lead paddock presenter, the senior form and speed analyst, the Bayesian edge and Kelly modeler, and the trackside scout, each mapped to its assigned voice.

### Requirement: Dynamic Script Generation
- The backend MUST expose `POST /api/podcast/generate` accepting `track`, `raceNumber`, and `runners` payload.
- The generation engine MUST analyze real contenders and yield structured JSON containing episode title, headline, summary points, and dialogue turns mapped to the 4 specialist roles.

#### Scenario: Generate endpoint returns a structured episode
- **WHEN** a client POSTs `track`, `raceNumber`, and `runners` to `/api/podcast/generate`
- **THEN** the engine SHALL return structured JSON containing the episode title, headline, summary points, and dialogue turns mapped to the four specialist roles.

### Requirement: Per-Turn Voice Audio Synthesis
- The backend MUST expose `POST /api/podcast/synthesize-line` to synthesize individual dialogue turns using Gemini TTS (`gemini-3.1-flash-tts-preview`) with assigned character voices.
- Audio MUST be encoded into standard PCM/WAV format for seamless browser playback.

#### Scenario: Dialogue turn is synthesized in the assigned voice
- **WHEN** a dialogue turn is submitted to `/api/podcast/synthesize-line`
- **THEN** Gemini TTS (`gemini-3.1-flash-tts-preview`) SHALL render it in the assigned character voice and the audio SHALL be encoded as standard PCM/WAV for browser playback.

### Requirement: Interactive HUD Player Experience
- The frontend MUST provide `SwarmPodcastView` featuring:
  - Master episode audio player with play/pause/skip/restart controls.
  - Synchronized speaker avatar, role badge, and dynamic audio wave indicator.
  - Interactive clickable transcript allowing instant jump to any speaker turn.
  - Race and track switcher pulling from live HUD race feeds.

#### Scenario: Listener navigates the episode in the HUD
- **WHEN** a user opens `SwarmPodcastView`
- **THEN** they SHALL have master playback controls, a synchronized speaker avatar, role badge and audio wave indicator, a clickable transcript that jumps to any speaker turn, and a race and track switcher fed by the live HUD.
