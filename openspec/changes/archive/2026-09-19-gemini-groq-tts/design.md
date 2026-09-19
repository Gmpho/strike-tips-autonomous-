# Design: Natural Text-to-Speech (Gemini & Groq)

## Architecture Overview

```
User / UI (HUD / Chat / Voice Studio)
       │
       ▼ POST /api/tts { text, provider: "gemini"|"groq", voice, style }
       │
   Server / Middleware (/api/tts)
       ├── Provider: "gemini"
       │     └─► @google/genai (model: "gemini-3.1-flash-tts-preview")
       │           └─► 24kHz PCM linear audio
       │                 └─► pcmToWavBuffer() ──► RIFF WAV Audio (audio/wav)
       │
       └── Provider: "groq"
             └─► https://api.groq.com/openai/v1/audio/speech (model: "canopylabs/orpheus-v1-english")
                   └─► Sentence chunking (<200 chars) + stitchWavBuffers()
                         └─► RIFF WAV Audio (audio/wav)
```

## Security & API Key Isolation
- `GEMINI_API_KEY` and `GROQ_API_KEY` remain strictly server-side.
- The client receives either binary `audio/wav` or `{ audioUrl, format, provider, voice }`.

## Voice Profiles
- **Gemini TTS**:
  - `Kore`: Balanced, warm, natural female voice.
  - `Puck`: Crisp, clear, friendly neutral male voice.
  - `Charon`: Deep, authoritative, calm baritone.
  - `Fenrir`: Energetic, crisp, analytical male voice.
  - `Zephyr`: Bright, upbeat, natural female voice.
- **Groq TTS** (`canopylabs/orpheus-v1-english`):
  - `autumn`: Conversational female voice.
  - `diana`: Formal, crisp female announcer.
  - `hannah`: Expressive, warm female voice.
  - `austin`: Dynamic, clear male voice.
  - `daniel`: Smooth, natural male narrator.
  - `troy`: Confident, radio-style male commentator.
