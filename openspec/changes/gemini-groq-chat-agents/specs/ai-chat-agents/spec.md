# Capability: AI Chat Agents, Search Grounding & Voice

## Requirements

### Multi-Turn Chat
- The application MUST provide a multi-turn chat interface maintaining message history across user sessions.
- The application MUST support role-based system instructions guiding the AI as a South African horse racing specialist and bankroll governor.
- The model selection MUST include:
  - `gemini-3.5-flash`: General multi-turn racing analysis with Google Search grounding.
  - `gemini-3.1-pro-preview`: Complex mathematical and exotics reasoning.
  - `gemini-3.1-flash-lite`: Fast-paced responses and casual lookups.
  - `llama-3.3-70b-versatile` (Groq): Ultra-fast token generation.

### Search Grounding
- For real-time racing queries, `gemini-3.5-flash` MUST support Google Search grounding via the `googleSearch` tool.
- Grounded responses MUST display source citations and search entry point links where available.

### Audio Transcription
- Users MUST be able to record speech from their microphone.
- Audio MUST be transcribed using `gemini-3.5-transcribe` (with optional Groq Whisper).
- Transcriptions MUST populate the chat input field or auto-submit.

### Live Voice Conversations
- The application MUST offer a real-time conversational voice mode powered by `gemini-3.8-live`.
- Real-time audio MUST stream bidirectionally with interruption handling and clear visual activity indicators.
