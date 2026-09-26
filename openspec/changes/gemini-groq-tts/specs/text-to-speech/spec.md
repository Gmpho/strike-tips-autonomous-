# Capability: Text to Speech (TTS)

## Purpose
Provides natural-sounding neural text-to-speech synthesis using Gemini TTS and Groq Speech APIs, converting race verdicts, market overviews, form analysis, and custom text into high-fidelity spoken audio.

## Requirements

### Requirement: Server-Side TTS Endpoint
The server MUST expose a `/api/tts` endpoint that accepts JSON payloads:
- `text` (string, required): The text to synthesize into speech.
- `provider` (string, optional): `"gemini"` | `"groq"` | `"auto"`. Defaults to `"gemini"`.
- `voice` (string, optional): Selected voice persona (e.g. `Kore`, `Puck`, `Charon`, `Fenrir`, `Zephyr` for Gemini; `autumn`, `diana`, `hannah`, `austin`, `daniel`, `troy` for Groq).
- `format` (string, optional): Audio output format (`"wav"`).

### Requirement: Gemini Natural TTS
When `provider` is `"gemini"`:
- The server MUST use the `@google/genai` SDK with model `gemini-3.1-flash-tts-preview`.
- The server MUST configure `responseModalities: [Modality.AUDIO]` and `speechConfig.voiceConfig.prebuiltVoiceConfig`.
- The server MUST convert the returned 24kHz linear PCM data into standard RIFF WAV format with a valid 44-byte header before returning to the client.

### Requirement: Groq Speech Synthesis
When `provider` is `"groq"`:
- The server MUST call the Groq Speech API endpoint `https://api.groq.com/openai/v1/audio/speech` using model `canopylabs/orpheus-v1-english`.
- If input exceeds the model limit (200 characters), the server MUST split the text cleanly into sentences and stitch resulting WAV chunks into a single gapless WAV stream.
- If `GROQ_API_KEY` is missing, the server MUST provide an informative error and gracefully offer or fallback to Gemini TTS.

### Requirement: Frontend Integration & Voice Studio
- The HUD MUST support direct voice playback in the AI Chat verdicts using natural voice synthesis.
- The HUD MUST feature a dedicated Text to Speech converter view with:
  - Input text area with quick templates (e.g., race summaries, value verdicts, tips).
  - Provider switcher (Gemini TTS vs Groq TTS).
  - Natural voice selector with gender and timbre indicators.
  - Vocal style/expression modifiers (e.g., cheerful, dramatic, neutral).
  - Audio playback controls (play, pause, seek, speed 0.75x–1.5x) and WAV audio download.
