## Phase 1: Gemini & Groq Chat Agents with Search Grounding

- [x] 1.1 Implement server-side chat service (`strike-tips-hud/server/chat-service.ts`) supporting `gemini-3.5-flash` with Google Search grounding, `gemini-3.1-pro-preview`, `gemini-3.1-flash-lite`, and Groq `llama-3.3-70b-versatile`
- [x] 1.2 Add `/api/chat` route to Vite dev server plugin and middleware proxy
- [x] 1.3 Update `strike-tips-hud/src/components/AIChat.tsx` model selector to include the new specialized Gemini and Groq models
- [x] 1.4 Render Google Search grounding citations and sources below chat messages

## Phase 2: Audio Transcription (gemini-3.5-transcribe & Groq Whisper)

- [x] 2.1 Implement server-side transcription service (`strike-tips-hud/server/transcribe-service.ts`) with `gemini-3.5-transcribe` and Groq `whisper-large-v3`
- [x] 2.2 Wire `/api/transcribe` endpoint in Vite server plugin
- [x] 2.3 Create frontend audio recording hook (`strike-tips-hud/src/hooks/useAudioRecorder.ts`) using browser `MediaRecorder`
- [x] 2.4 Add microphone button and recording state to `AIChat.tsx` input bar

## Phase 3: Real-Time Voice Conversations (gemini-3.8-live)

- [x] 3.1 Implement WebSocket Live API bridge (`strike-tips-hud/server/live-service.ts`) for `gemini-3.8-live`
- [x] 3.2 Wire WebSocket live endpoint in Vite server
- [x] 3.3 Create interactive Live Voice modal (`strike-tips-hud/src/components/LiveVoiceModal.tsx`) with audio visualizer, mic stream, and interruption handling
- [x] 3.4 Add Live Voice trigger to `AIChat.tsx` and `TextToSpeechView.tsx`

## Phase 4: Verification & OpenSpec Archive

- [x] 4.1 Verify TypeScript compilation (`tsc && vite build`) and linting
- [x] 4.2 Validate chat generation, search grounding, voice transcription, and live speech
- [x] 4.3 Update tasks and document user guide
