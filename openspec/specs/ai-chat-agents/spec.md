# ai-chat-agents Specification

## Purpose
TBD - created by archiving change gemini-groq-chat-agents. Update Purpose after archive.

## Requirements

### Requirement: Multi-Turn Chat

- The application MUST provide a multi-turn chat interface maintaining message history across user sessions.
- The application MUST support role-based system instructions guiding the AI as a South African horse racing specialist and bankroll governor.
- The model selection MUST include:
  - `gemini-3.5-flash`: General multi-turn racing analysis with Google Search grounding.
  - `gemini-3.1-pro-preview`: Complex mathematical and exotics reasoning.
  - `gemini-3.1-flash-lite`: Fast-paced responses and casual lookups.
  - `llama-3.3-70b-versatile` (Groq): Ultra-fast token generation.

#### Scenario: Follow-up message keeps history and honours the selected model

- **WHEN** a user sends a follow-up message in an existing conversation
- **THEN** the prior messages SHALL be retained in context and the reply SHALL come from the selected model using the racing-specialist and bankroll-governor system instructions.

### Requirement: Search Grounding

- For real-time racing queries, `gemini-3.5-flash` MUST support Google Search grounding via the `googleSearch` tool.
- Grounded responses MUST display source citations and search entry point links where available.

#### Scenario: Grounded answer surfaces its citations

- **WHEN** a real-time racing query is answered by `gemini-3.5-flash` with grounding enabled
- **THEN** the response SHALL display the source citations and search entry point links returned by the provider.

### Requirement: Audio Transcription

- Users MUST be able to record speech from their microphone.
- Audio MUST be transcribed using `gemini-3.5-transcribe` (with optional Groq Whisper).
- Transcriptions MUST populate the chat input field or auto-submit.

#### Scenario: Recorded speech becomes chat input

- **WHEN** the user records speech from the microphone
- **THEN** the audio SHALL be transcribed and the resulting text SHALL populate the chat input field or auto-submit.

### Requirement: Live Voice Conversations

- The application MUST offer a real-time conversational voice mode powered by `gemini-3.8-live`.
- Real-time audio MUST stream bidirectionally with interruption handling and clear visual activity indicators.

#### Scenario: Bidirectional voice with interruption handling

- **WHEN** live voice mode is active
- **THEN** audio SHALL stream in both directions, interruption SHALL be handled, and the interface SHALL show a clear activity indicator.
