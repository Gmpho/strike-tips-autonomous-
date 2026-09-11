## Why

Mobile browsers and PWA/TWA installs need on-device AI that works offline after a single Wi-Fi download, without porting fork code. The current HUD has no Transformers.js, no TTS/translation/TrOCR, and no offline pack, and WebLLM hits raw GitHub 503s.

## What Changes

* **Summarize:** resident Qwen toggle reusing existing WebLLM singleton, no RAG.
* **Sentiment:** DistilBERT q4 worker + News badges (on-demand, ~110MB).
* **TTS:** Supertonic + 3 voices + speaker buttons + Cycle Voice.
* **Translation:** Opus-MT en→af + m2m100 zu + NLLB sot_Latn, per-language toggles.
* **TrOCR:** int8 form reader + image attach → text into chat input.
* **Offline pack:** Settings bulk Wi-Fi download with progress + per-model status.
* **Production:** jsDelivr mirror fix for `binary-mlc-llm-libs`, Vite worker `?worker` imports, COOP/COEP headers, quota gates.
* **Chat freeze:** 100ms token batch, debounced persisted history (50/2s), rAF sticky scroll, weak-GPU guard, GPU-loss fallback.

## Capabilities

### New Capabilities
- `mobile-browser-ai`: on-device summarize, sentiment, TTS, translation, TrOCR, offline pack, and production browser-AI hardening.

### Modified Capabilities
- `web-llm` (existing browser-AI): mirror fix and chat performance.

## Impact

* `strike-tips-hud/src/lib/offline-models.ts`, `offline-pack.ts`, `worker-client.ts`, `webllm.ts` (mirror)
* `strike-tips-hud/src/workers/*` (sentiment, tts, translate, trocr)
* `strike-tips-hud/src/hooks/useSentiment|TTS|Translation|FormReader`
* `strike-tips-hud/src/components/AIChat.tsx`, `NewsView.tsx`, `SettingsView.tsx`
* `strike-tips-hud/vercel.json`, `vite.config.ts`, `public/sw.js`
