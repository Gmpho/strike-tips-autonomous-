# Design: Zero-Buffer Swarm Podcast & Hands-Free Gemma 4 Voice

## Architecture

```
[ Episode Loaded ] ──► Dialogue Lines [ L0, L1, L2, L3, ... Ln ]
                              │
       ┌──────────────────────┴──────────────────────┐
       ▼                                             ▼
(Active Playback)                             (Lookahead Pre-fetch Queue)
L0 Audio Playing...                           fetchAudio(L1), fetchAudio(L2) in parallel
       │                                             │
       ▼ (onended)                                   ▼
L0 Finishes ──────► Audio for L1 already in Cache ──► Starts L1 immediately (0ms gap)
                    Pre-fetch worker requests L3
```

## Podcast Multi-Engine Flow (`podcast-service.ts`)
- **Engine: Google AI Studio Gemma 4**: Deep racing storyline & exotics reasoning. Generates script using `gemma-2-27b-it` / `gemma-4-31b-it`.
- **Engine: Groq LPUs**: Ultra-fast generation using `qwen/qwen3.8-27b` or `llama-3.3-70b-versatile` in $< 1$ second.
- **Engine: Gemini 3.5 Flash**: Default multimodal and search grounded episode generation.

## Chat Auto-Voice Flow (`AIChat.tsx`)
```
[ User Speaks (Mic) or Types ] ──► Model Streams Response (e.g. Gemma 4 / Groq Qwen)
                                               │
                                               ▼
                              (Stream Finishes: [DONE])
                                               │
                                 Is autoSpeak enabled?
                                   ├── YES ──► onSpeakMessage(finalText) automatically
                                   └── NO  ──► Wait for manual speaker click
```
