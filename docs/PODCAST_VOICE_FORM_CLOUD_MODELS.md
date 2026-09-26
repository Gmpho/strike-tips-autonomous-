# 🎙️ Swarm Podcast, Voice Chat & Form PDF Ingestion

This document details the Zero-Buffer Autonomous Swarm Podcast, Hands-Free Auto-Voice Chat with Gemma 4, Decoupled PDF/Form Ingestion, and Groq/Google AI Studio Cloud Model routing implemented for Strike Tips.

---

## 🚀 Architectural Highlights

```
                                      ┌───────────────────────────────────────────────┐
                                      │              USER INTERACTIONS                │
                                      └───────┬───────────────────────────────┬───────┘
                                              │                               │
                                   [ Upload Form / PDF ]              [ Mic / Voice Chat ]
                                              │                               │
                                              ▼                               ▼
                                  form-reader-service.ts              AIChat [Auto-Voice]
                                  (Decoupled from core)                       │
                                              │                               ▼
                                              ├─────────────────────► Gemma 4 / Groq Qwen
                                              │                               │
                                              ▼                               ▼
                                     Structured Markdown              Natural Voice TTS
                                      & Action Chips                  (Hands-Free Paddock)
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     │                                                 │
                     ▼                                                 ▼
          [ Swarm Podcast Generator ]                      [ Zero-Buffer Player ]
          - Gemma 4 (Deep Reasoning)                       - Lookahead Pre-fetch Queue
          - Groq LPUs (<800ms generation)                  - N+1, N+2 synthesized ahead
          - 5-Agent Autonomous Roster                      - 0ms Gapless Radio Playback
```

---

## 1. 📻 Zero-Buffer Swarm Podcast Engine

### The Problem
Previously, dialogue lines were synthesized sequentially on-demand. When an agent finished speaking, audio playback halted for 2–4 seconds while the next line was requested and encoded over the network, causing noticeable silence and stutter.

### The Zero-Buffer Lookahead Architecture
Implemented in `strike-tips-hud/src/components/SwarmPodcastView.tsx`:
1. **Parallel Background Pre-fetching**:
   - As soon as Line $N$ begins playing, background workers eagerly fetch and synthesize audio for Line $N+1$ and Line $N+2$.
   - Responses are cached as Blob URLs in `audioCacheRef`.
2. **In-Flight Deduplication**:
   - An active promise map (`inFlightFetches`) ensures duplicate network requests are never dispatched if a pre-fetch is already underway.
3. **Eager Opening Pre-fetch**:
   - Lines 0 and 1 are synthesized immediately upon script generation or episode load, eliminating opening latency.
4. **Gapless Radio Transition**:
   - When the native HTML5 audio `onended` event fires, Line $N+1$ begins playback with **0ms buffering gap** directly from client memory.

---

## 2. 👥 5-Agent Swarm Cast & Multi-Engine Scripting

### Swarm Specialist Personas
The podcast roundtable features 5 specialized autonomous AI agents:

| Persona | Role Title | Voice Model | Focus Domain |
|---|---|---|---|
| **Sipho Ndlovu** | Lead Paddock Presenter | `Kore` | Energetic anchor, moderates discussion, frames prices |
| **Gareth Vance** | Senior Form Analyst | `Charon` | Draw bias, turn of foot, course geometry, jockey strike rates |
| **Dr. Elena Becker** | Bayesian Edge Modeler | `Zephyr` | Quantitative odds, Half-Kelly bankroll exposure, Monte Carlo edges |
| **Tebogo Molefe** | Trackside Scout | `Puck` | Going pen reading, paddock demeanor, pre-race sweat, rail bias |
| **Gemma AI** | Exotic Permutation Specialist | `Fenrir` | **Gemma 4** exotic permutations, Pick 6 bankers, scenario analysis |

### Multi-Engine Script Generation (`/api/podcast/generate`)
Users can choose their preferred scriptwriting engine in the Podcast HUD header:
*   🧠 **Gemma 4 (Google AI Studio · 1,500 Free Daily)**: Leverages `gemma-2-27b-it` / `gemma-4-31b-it` for deep racing storylines, historical nuance, and intricate exotic structures.
*   ⚡ **Groq Cloud LPUs (Sub-Second)**: Uses `qwen/qwen3.8-27b` or `llama-3.3-70b-versatile` to generate complete 6–8 turn JSON episodes in under **800ms**.
*   ✨ **Gemini 3.5 Flash**: Default multimodal engine with live Google Search grounding for scratchings and morning track weather.

### Live Race Selection & Deep Metadata Ingestion
The podcast selector now connects directly to individual live contests on today's racing card:
*   **Rich Race Selector**: Instead of choosing only a track, users select specific contests: `🏇 Kenilworth · Race 3 @ 13:15 (1200m) · 8 runners`.
*   **Live Context Forwarding**: The request to `/api/podcast/generate` transmits distance in metres (e.g. `1200m Sprint`), post time, risk volatility category, and Dream Stress Index (DSI).
*   **Enriched Runner Dimensions**: Every runner is passed with their draw stall, jockey, trainer, Betfair gear tokens (e.g. `Blinkers · Pacifiers`), and days since last run.
*   **Live Race Targeted Strip**: Renders a dedicated status bar showing `🔴 LIVE RACE TARGETED`, course, distance, post time, field size, DSI, and the top value edge runner in real time.

---

## 3. 🎙️ Hands-Free Auto-Voice Chat with Gemma 4

### The Workflow
Designed for trackside punters and drivers who cannot stare at screens:
1. **Auto-Voice Toggle (`[📻 AUTO-VOICE]`)**:
   - Accessible in the chat toolbar; state persists via `localStorage`.
   - Glowing purple pulse indicates hands-free mode is armed.
2. **Conversational Audio Loop**:
   - Punter taps the microphone and speaks their question (transcribed in $\sim 200$ms via Groq Whisper).
   - **Gemma 4 31B** (or Groq Qwen 3.8) streams high-IQ racing analysis.
   - The moment the stream completes, **Auto-Voice automatically triggers speech synthesis** using the user's selected neural voice (`tts.currentVoice`), speaking the verdict aloud without requiring any screen interaction.

---

## 4. 📄 Decoupled Form, Computaform & PDF Ingestion

### Preserving Automated Scrapers (L7 Invariant)
*   **Rule**: `core_agent/skills/parsers/pdf_harvester.py` remains **strictly untouched** to preserve background Azure TAB automated harvest routines.
*   **Isolated Service**: Implemented `strike-tips-hud/server/form-reader-service.ts` exclusively for user-uploaded documents.

### Ingestion Capabilities
*   **Multi-Format Acceptance**: Accepts `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp` (TAB Computaforms, Sporting Post tipping sheets, steward notices).
*   **Visual File Preview Chip**: Shows an attached file badge (`[📄 Computaform_Kenilworth.pdf (PDF Racecard) ✖]`) with instant removal.
*   **Executive Meeting Overview**: If a document is uploaded without explicit betting instructions, the system presents an executive summary (track, rail, going, contenders) rather than forcing unsolicited bets.
*   **Interactive Action Chips**:
    *   `🎯 Top Value Picks`: Calculates probability edge against market prices + Half-Kelly stake.
    *   `⚡ Pace & Draw Bias`: Analyzes track layout, draw advantages, and tactical pace.
    *   `📋 Condensed Table`: Formats a clean markdown runner cheat sheet.

---

## 5. 🛠️ Cloud Model Routing Reference

| Model Display Name | Provider | Internal ID | Optimal Use Case |
|---|---|---|---|
| **Gemma 4 · 31B** | Google AI Studio | `gemma-4-31b` / `gemma-2-27b-it` | Deep form analysis, steward reasoning, exotics |
| **Gemini 3.5 Flash** | Google AI Studio | `gemini-3.5-flash` | Live web search grounding & native PDF parsing |
| **Gemini 3.8 Flash** | Google AI Studio | `gemini-3.8-flash` | Multimodal racecard master |
| **Gemini 3.1 Pro** | Google AI Studio | `gemini-3.1-pro-preview` | Complex mathematical proofs & Kelly staking |
| **Groq · Qwen 3.8 27B** | Groq Cloud | `qwen/qwen3.8-27b` | Elite racecard & tabular summarizer (~400 t/s) |
| **Groq · Qwen 3.6 27B** | Groq Cloud | `qwen/qwen3.6-27b` | Rapid steward reports & form parser |
| **Groq · Gemma 2 9B** | Groq Cloud | `gemma2-9b-it` | Ultra-fast Google architecture on Groq |
| **Groq · Llama 3.3 70B**| Groq Cloud | `llama-3.3-70b-versatile` | General versatile racing intelligence |

---

## 6. 📜 OpenSpec Artifacts

All work was executed under OpenSpec guidelines:
*   `openspec/changes/racing-form-pdf-and-cloud-models/`
*   `openspec/changes/podcast-zero-buffer-gemma4-voice/`
