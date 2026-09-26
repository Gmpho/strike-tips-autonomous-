# Design: Racing Form & PDF Ingestion with Groq Qwen & Google AI Studio

## Architecture Overview

```
User attaches PDF or Image in HUD (AIChat.tsx)
                  │
                  ▼
         POST /api/chat (SSE Stream)
     { messages, model, attachment: { mimeType, data, name }, summarizeMode }
                  │
                  ├── If model is Google AI Studio (Gemini / Gemma):
                  │     └── Sends inlineData directly to @google/genai (Native PDF & Vision)
                  │
                  └── If model is Groq (Qwen 3.8/3.6 27B, Gemma 2 9B, Llama 70B):
                        └── form-reader-service extracts text / tables from PDF or image
                        └── Injects structured Markdown table into Groq user prompt
                        └── Groq LPUs stream completions at 300+ tokens/sec
```

## Key Invariants
1. **Preservation of `core_agent/skills/parsers/pdf_harvester.py`**: Background Azure TAB scrapers remain unaffected. All user-driven uploads use the new isolated `strike-tips-hud/server/form-reader-service.ts`.
2. **Deterministic Summarizer vs. Betting Logic**:
   - If user uploads a form without explicit bet requests: Provide Executive Overview + interactive chips (`🎯 Top Value Picks`, `⚡ Pace & Bias`, `📋 Full Table`).
   - If user clicks a chip or asks for value picks: Run probability edge calculation and Half-Kelly recommendations.
3. **Quota Optimization**:
   - Highlight Google AI Studio models (1,500 requests/day reset) as the primary multimodal/PDF engine.
   - Highlight Groq LPUs as the high-speed text/summarizer engine.
