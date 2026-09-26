## Why

The current text-to-speech implementation in Strike Tips HUD relied exclusively on a client-side SpeechT5 ONNX model inside a Web Worker. This approach required downloading ~130MB of model weights and voice vectors, causing high latency, storage quota exhaustion, and a robotic/synthetic voice tone. Users need fast, natural-sounding, neural speech synthesis powered by Gemini TTS (`gemini-3.1-flash-tts-preview`) and the Groq Speech API (`canopylabs/orpheus-v1-english`) for listening to racing verdicts, racecard summaries, analysis notes, and custom text aloud.

## What Changes

- Implement a secure server-side TTS endpoint `/api/tts`:
  - Natural-sounding speech with Gemini TTS using `@google/genai` model `gemini-3.1-flash-tts-preview` with voices (Kore, Puck, Charon, Fenrir, Zephyr), returning clean WAV audio.
  - Expressive speech with Groq TTS via `https://api.groq.com/openai/v1/audio/speech` using `canopylabs/orpheus-v1-english` with voices (autumn, diana, hannah, austin, daniel, troy), supporting vocal direction tags and chunk stitching for longer racing verdicts.
  - Graceful fallback: If Groq is selected but no GROQ_API_KEY is configured, system provides helpful guidance and automatically falls back to Gemini TTS.
- Update `.env.example` to document `GROQ_API_KEY`.
- Refactor frontend `useTTS` hook and TTS utilities in `strike-tips-hud`:
  - Add cloud-backed natural voice synthesis via `/api/tts` with instant playback, no 130MB download required.
  - Support both Gemini TTS and Groq TTS engine selection and diverse character voice presets.
  - Seamless audio playback with play, pause, stop, speed controls, and WAV download.
- Provide a dedicated Natural Speech & Text-to-Speech Studio in the HUD:
  - Accessible from the sidebar / tools navigation as "Text to Speech" / "Voice Studio" as well as from the AI Chat verdict speak action.
  - Allows entering or pasting race cards, tips, summaries, or custom text with natural speech synthesis.
  - Voice selector with audio preview, engine switcher (Gemini TTS vs Groq TTS), emotional style controls (`[cheerful]`, `[dramatic]`, etc.), audio wave visualizer, and instant playback.
- Update AI Chat verdict read-aloud buttons to use natural neural TTS.

## Capabilities

### New Capabilities
- `text-to-speech`: Real-time neural voice conversion using Gemini TTS and Groq Speech APIs with natural timbre, selectable voices, and audio streaming/download.

## Impact

- **Backend & Middleware**: Server-side `/api/tts` handler in Vite server dev/preview and `middleware.ts`.
- **Frontend HUD**: `strike-tips-hud/src/hooks/useTTS.ts`, `strike-tips-hud/src/components/AIChat.tsx`, `strike-tips-hud/src/components/TextToSpeechView.tsx`, `strike-tips-hud/src/App.tsx`, `strike-tips-hud/src/components/sidebar/Sidebar.tsx`.
- **Configuration**: `.env.example`, `package.json`.
