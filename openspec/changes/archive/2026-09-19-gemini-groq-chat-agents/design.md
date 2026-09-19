# Design: Gemini & Groq AI Chat Agents with Voice, Search Grounding & Transcription

## Architecture Overview

```
                        ┌────────────────────────────────────────┐
                        │        Strike Tips HUD (React)         │
                        │                                        │
                        │  AIChat.tsx    Voice Studio            │
                        │   - Mic Input    - Live Mode Modal     │
                        │   - Citations    - Model Selector      │
                        └───────┬────────────┬─────────────┬─────┘
                                │            │             │
                    POST /api/chat     POST /api/transcribe  WS /api/live
                                │            │             │
        ┌───────────────────────▼────────────▼─────────────▼──────────────┐
        │                 Vite Server / FastAPI Proxy                      │
        │                                                                 │
        │   chat-service.ts       transcribe-service.ts   live-service.ts │
        └───────┬────────────────────────────┬─────────────────────┬──────┘
                │                            │                     │
    ┌───────────▼────────────┐  ┌────────────▼─────────┐ ┌─────────▼───────────┐
    │     Gemini & Groq      │  │ Gemini Transcribe &  │ │   Gemini Live API   │
    │                        │  │     Groq Whisper     │ │                     │
    │ • gemini-3.5-flash     │  │                      │ │ • gemini-3.8-live   │
    │   (+ googleSearch)     │  │ • gemini-3.5-        │ │ • 16kHz PCM In      │
    │ • gemini-3.1-pro-prev  │  │   transcribe         │ │ • 24kHz PCM Out     │
    │ • gemini-3.1-flash-lite│  │ • whisper-large-v3   │ │ • Interruption mgmt │
    │ • llama-3.3-70b        │  └──────────────────────┘ └─────────────────────┘
    └────────────────────────┘
```

## Phase 1: Chat Architecture & Search Grounding
- Client calls `/api/chat` with `{ messages, model, searchGrounding?: boolean, systemInstruction?: string }`.
- When `gemini-3.5-flash` is used and search grounding is enabled:
  ```typescript
  const response = await ai.models.generateContent({
    model: 'gemini-3.5-flash',
    contents: contentsList,
    config: {
      systemInstruction: roleInstruction,
      tools: [{ googleSearch: {} }]
    }
  });
  ```
- Citations & sources are extracted from `candidate.groundingMetadata?.groundingChunks` and returned alongside the response text.
- Groq models route via `https://api.groq.com/openai/v1/chat/completions` with streaming tokens.

## Phase 2: Audio Transcription Architecture
- Client captures microphone audio using standard `MediaRecorder` encoded as `audio/webm` or `audio/wav`.
- POSTs audio Blob / base64 payload to `/api/transcribe`.
- Server handles transcription:
  - Gemini: `gemini-3.5-transcribe` receives base64 data and mimeType, returning exact text.
  - Groq: multipart `whisper-large-v3` transcription.
- Client receives `{ text: "..." }` and updates the chat input with the transcribed query.

## Phase 3: Real-Time Live Voice Conversation (Live API)
- WebSocket connection established to `/api/live` (or directly bridging via server Live session).
- Model: `gemini-3.8-live` with `responseModalities: [Modality.AUDIO]`.
- Input: 16kHz PCM audio streaming from user microphone.
- Output: 24kHz PCM audio chunks streamed back to client and scheduled through Web Audio `AudioBufferSourceNode`.
- UI modal shows active conversational waveform, speaking states, and live transcript.
