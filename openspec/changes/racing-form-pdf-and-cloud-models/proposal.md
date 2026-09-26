# Change: Racing Form & PDF Ingestion with Groq Qwen & Google AI Studio Models

## Why

1. **User Form & PDF Reading**: Punters need to attach official TAB Computaform sheets, Sporting Post tipping sheets, racecard images, or steward reports. Currently, form reading relies on client-side TrOCR which fails on 2D tabular racecard layouts and lacks PDF support.
2. **Groq Qwen Models**: Users want high-throughput inference with `qwen/qwen3.8-27b` and `qwen/qwen3.6-27b` (as well as `gemma2-9b-it`) on Groq LPUs for rapid racecard digestion and steward report summarization.
3. **Google AI Studio (1,500 Free Requests/Day)**: Google AI Studio provides generous per-day reset quotas (1,500 RPD) and native multimodal PDF understanding (Gemini 3.5/3.8 Flash and Gemma models), avoiding credit burn while handling multi-page race documents.
4. **Smart Summarize vs. Value Picks**: When users upload a racecard or paste text without specific instructions, the system should present an Executive Meeting Summary (track, going, key storylines) along with interactive quick-action chips (`🎯 Top Value Picks`, `⚡ Pace & Bias`, `📋 Full Table View`) rather than forcing unsolicited bets.
5. **Decoupled Architecture**: Per L7 design rules, `core_agent/skills/parsers/pdf_harvester.py` must remain completely untouched to preserve the automated background ingest pipeline. User uploads will be handled through a dedicated, isolated service.

## What Changes

### 1. Model Selector & Cloud Gateway
- Expand `strike-tips-hud/src/components/AIChat.tsx` model dropdown to include:
  - **Google AI Studio (1,500 RPD)**: `gemini-3.5-flash` (Search Grounding & PDF), `gemini-3.8-flash`, `gemini-3.1-pro-preview`, `gemma-4-31b-it` / `gemma-2-27b-it`.
  - **Groq Cloud LPUs**: `groq-qwen-3.8-27b` (`qwen/qwen3.8-27b`), `groq-qwen-3.6-27b` (`qwen/qwen3.6-27b`), `groq-gemma2-9b` (`gemma2-9b-it`), `groq-llama-70b` (`llama-3.3-70b-versatile`), `groq-llama-8b` (`llama-3.1-8b-instant`).
- Update `strike-tips-hud/server/chat-service.ts` to route Groq Qwen and Gemma requests, accept base64 attachments (images and PDFs), and stream SSE responses.

### 2. Form & PDF Ingestion Pipeline
- Update `AIChat.tsx` file picker to accept `image/*,application/pdf,.pdf`.
- Support visual attachment chips with document icon, filename, and remove button.
- For Gemini models: pass PDF and image data directly via `inlineData`.
- For Groq models: pre-extract text and table layout using a clean server-side document utility, feeding structured Markdown tables into Qwen/Gemma.

### 3. Smart Racing Summarizer & Action Chips
- When `summarizeMode` is active or a form is uploaded without specific betting prompts, provide an Executive Racecard Overview with:
  - Meeting conditions (track, rail, going, distance profile).
  - Key contenders and weight/MR changes.
  - Interactive quick-action buttons below the assistant response (`🎯 Find Top Value Picks`, `⚡ Pace & Draw Bias`, `📋 Print Condensed Table`).

## Capabilities
- `racing-form-pdf-ingestion`: Support for user-uploaded TAB Computaform, tipping sheets, and racing PDFs with table extraction.
- `groq-qwen-cloud-models`: High-throughput Groq Qwen 3.8/3.6 27B and Gemma 2 9B model routing.
- `google-ai-studio-models`: Multi-modal Gemini and Gemma models utilizing Google AI Studio 1,500 free daily requests.

## Impact
- `strike-tips-hud/src/components/AIChat.tsx`
- `strike-tips-hud/server/chat-service.ts`
- `strike-tips-hud/server/form-reader-service.ts` (new isolated document helper)
- `core_agent/skills/parsers/pdf_harvester.py` (STRICTLY UNTOUCHED)
