## 1. Core browser-AI plumbing

- [x] 1.1 `offline-models` registry + `ensureStorageFor` quota gate + consent
- [x] 1.2 `worker-client` shared helper (progress fan-out, timeouts, termination)
- [x] 1.3 Mirror fix for `binary-mlc-llm-libs` (jsDelivr, no doubled `/main`)
- [x] 1.4 `vercel.json` COOP/COEP + `vite.config.ts` exclude

## 2. Summarize

- [x] 2.1 AIChat toggle, brief swap, no history/RAG when on

## 3. Sentiment

- [x] 3.1 `sentiment.worker.ts` (DistilBERT q4) + `useSentiment` + News badges

## 4. TTS

- [x] 4.1 `tts.worker.ts` (Supertonic) + `useTTS` (3 voices, cache) + speaker buttons

## 5. Translation

- [x] 5.1 `translate.worker.ts` (Opus-MT/m2m100/NLLB) + `useTranslation` + verdict translate UI

## 6. TrOCR

- [x] 6.1 `trocr.worker.ts` (int8) + `useFormReader` + image attach → input

## 7. Offline pack + polish

- [x] 7.1 Settings bulk pack with progress + per-model status
- [x] 7.2 Chat freeze: 100ms batch, debounced persist (50/2s), rAF scroll, weak-GPU guard, GPU-loss fallback
- [x] 7.3 `tsc` clean, build, E2E (AF, sentiment, TTS audio, TrOCR, ZU)

## 8. Verify

- [x] 8.1 Deploy: `tsc` clean, prod build green, Vercel live
