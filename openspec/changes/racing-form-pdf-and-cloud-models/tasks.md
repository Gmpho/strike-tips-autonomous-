## Phase 1: Model Selection & Cloud Gateway Routing

- [x] 1.1 Update `strike-tips-hud/src/components/AIChat.tsx` model selector dropdown with Google AI Studio (Gemma 4 31B, Gemini 3.5/3.8 Flash, Pro) and Groq (Qwen 3.8 27B, Qwen 3.6 27B, Gemma 2 9B, Llama 70B/8B)
- [x] 1.2 Update `strike-tips-hud/server/chat-service.ts` to route Groq Qwen models (`qwen3.8-27b`, `qwen3.6-27b`), `gemma2-9b-it`, and Google AI Studio models
- [x] 1.3 Add attachment payload support (`mimeType`, `data`, `name`) in `chat-service.ts` for Gemini `inlineData` and Groq text injection

## Phase 2: PDF & Racecard Upload Support

- [x] 2.1 Create decoupled `strike-tips-hud/server/form-reader-service.ts` to parse user-uploaded PDFs and images into structured Markdown tables without touching `pdf_harvester.py`
- [x] 2.2 Update `AIChat.tsx` file input to accept `image/*,application/pdf,.pdf` with visual preview chip and remove button
- [x] 2.3 Wire PDF upload handling to send base64 data to `/api/chat`

## Phase 3: Smart Summarizer & Interactive Action Chips

- [x] 3.1 Update system instructions for Racecard Summarizer mode to output Executive Meeting Overviews when no explicit bets are requested
- [x] 3.2 Add interactive action chips (`🎯 Top Value Picks`, `⚡ Pace & Draw Bias`, `📋 Full Table View`) beneath chat responses
- [x] 3.3 Validate build compilation and test end-to-end flow
