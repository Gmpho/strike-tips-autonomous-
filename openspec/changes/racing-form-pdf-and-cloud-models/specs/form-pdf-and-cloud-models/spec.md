# Capability: Racing Form PDF Ingestion & Cloud Models

## Requirements

### Model Selection & Routing
- The HUD chat interface MUST offer:
  - Google AI Studio: `gemini-3.5-flash`, `gemini-3.8-flash`, `gemini-3.1-pro-preview`, `gemma-4-31b-it`.
  - Groq Cloud LPUs: `qwen/qwen3.8-27b`, `qwen/qwen3.6-27b`, `gemma2-9b-it`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`.
  - On-Device WebLLM (Llama 3.2 1B, Qwen 1.5B).
- Selecting any model MUST route correctly in `/api/chat` with SSE token streaming.

### Racecard & PDF Ingestion
- The file attachment control MUST accept both images (`image/*`) and PDF documents (`application/pdf`, `.pdf`).
- Attached files MUST display a removable preview chip indicating filename and type.
- Google AI Studio requests MUST forward PDFs and images as `inlineData` parts.
- Groq requests MUST extract tabular and text content via an isolated server-side reader prior to inference.

### Smart Summarization & Action Chips
- When a form or PDF is uploaded without specific queries, the assistant MUST respond with an Executive Racecard Overview.
- Responses MUST render interactive quick-action chips allowing users to seamlessly request:
  - `🎯 Find Top Value Picks`
  - `⚡ Pace & Draw Bias`
  - `📋 Condensed Table View`
