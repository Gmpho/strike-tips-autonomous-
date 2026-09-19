## 1. Environment & Server Endpoint

- [x] 1.1 Update `.env.example` with `GROQ_API_KEY`
- [x] 1.2 Implement server-side `/api/tts` handler supporting Gemini TTS (`gemini-3.1-flash-tts-preview`) and Groq TTS (`canopylabs/orpheus-v1-english`)
- [x] 1.3 Wire `/api/tts` in Vite server configuration and middleware routing

## 2. Frontend TTS Client & Hook Refactor

- [x] 2.1 Refactor `strike-tips-hud/src/hooks/useTTS.ts` to support cloud neural TTS (Gemini & Groq) with instant natural playback
- [x] 2.2 Add voice configurations, provider selection, and audio caching

## 3. UI Integration & Dedicated Voice Studio

- [x] 3.1 Create `strike-tips-hud/src/components/TextToSpeechView.tsx` with full TTS controls (text conversion, voice selection, expression tags, waveform display, speed control, download)
- [x] 3.2 Update `strike-tips-hud/src/App.tsx` and `Sidebar.tsx` to include the Text to Speech view
- [x] 3.3 Update `strike-tips-hud/src/components/AIChat.tsx` to utilize the natural speech engine

## 4. Verification

- [x] 4.1 Run linter and compiler verification
- [x] 4.2 Test TTS generation with Gemini and Groq
