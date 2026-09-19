# Change: Gemini & Groq AI Chat Agents with Voice, Search Grounding & Transcription

## Why

The current AI chat in Strike Tips HUD provides on-device WebLLM models and an auto-router, but lacks:
1. **Google Search Grounding**: Live horse racing events have dynamic factors (going changes, scratches, jockey changes, market fluctuations) that require fresh search data via `gemini-3.5-flash` with the `googleSearch` tool.
2. **Multi-Tier Model Specialization**: Dedicated roles for fast responses (`gemini-3.1-flash-lite`), general multi-turn racing analysis (`gemini-3.5-flash`), and complex mathematical/exotics reasoning (`gemini-3.1-pro-preview`), alongside Groq's high-throughput models (`llama-3.3-70b-versatile`).
3. **Audio Transcription**: Hands-free voice querying where punters can speak into their microphone and transcribe speech verbatim via `gemini-3.5-transcribe` (and Groq Whisper).
4. **Real-Time Live Voice Conversations**: Interactive low-latency two-way conversational audio using `gemini-3.8-live` (Live API).

## What Changes

### Phase 1: Multi-Turn Chat with Search Grounding & Specialized Models
- Server-side `/api/chat` route supporting:
  - `gemini-3.5-flash` with `googleSearch` grounding, returning markdown text and search citations/grounding sources.
  - `gemini-3.1-pro-preview` for complex exotics and calculations.
  - `gemini-3.1-flash-lite` for ultra-fast turns.
  - Groq `llama-3.3-70b-versatile` & `llama-3.1-8b-instant` for ultra-fast open-weight generation.
- Role-specific system instructions giving the chatbot expertise in South African racing, form evaluation, value betting, and Half-Kelly staking.
- Multi-turn conversation history persistence and visual citation chips for search-grounded responses.

### Phase 2: Audio Transcription
- Server-side `/api/transcribe` endpoint supporting:
  - Gemini: `gemini-3.5-transcribe` via `@google/genai`
  - Groq: `whisper-large-v3` via Groq Audio API
- Frontend microphone recording button in `AIChat.tsx` using `MediaRecorder`, with live recording state, waveform pulse, and auto-insert into chat input.

### Phase 3: Real-Time Live Voice Conversations (Live API)
- Real-time conversational audio with `gemini-3.8-live`.
- Interactive Voice Mode toggle in `AIChat.tsx` / `TextToSpeechView.tsx` with live audio streaming, interruption handling, and speech playback.

## Capabilities

### New Capabilities
- `ai-chat-agents`: Multi-turn Gemini and Groq racing agents with search grounding, model specialization, and role instructions.
- `audio-transcription`: Microphone recording and verbatim transcription via `gemini-3.5-transcribe` and Groq Whisper.
- `live-voice-conversation`: Real-time bidirectional voice conversations with `gemini-3.8-live`.

## Impact

- **Backend**: `/strike-tips-hud/server/chat-service.ts`, `/strike-tips-hud/server/transcribe-service.ts`, `/strike-tips-hud/server/live-service.ts`, Vite server handlers, FastAPI backend routes.
- **Frontend**: `strike-tips-hud/src/components/AIChat.tsx`, `strike-tips-hud/src/components/LiveVoiceModal.tsx`, `strike-tips-hud/src/hooks/useAudioRecorder.ts`.
- **OpenSpec**: Specifications and tasks documented under `openspec/changes/gemini-groq-chat-agents/`.
