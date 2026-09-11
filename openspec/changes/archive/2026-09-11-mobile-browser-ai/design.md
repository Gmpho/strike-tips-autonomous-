## Context

Browser AI must work on mid-range phones via PWA/TWA, fully offline after first Wi-Fi download, with one-resident-model VRAM discipline. The HUD already has a WebLLM singleton and OPFS cache; fork patterns are useful but code must be fresh.

## Goals / Non-Goals

**Goals:** summarize without download, sentiment/TTS/translation/TrOCR on-demand with honest sizes, offline pack, WebGPU/CPU fallbacks, no chat freeze.

**Non-Goals:** depth estimation, Florence-2, NLLB blob, full-page layout, African-language TTS, porting fork code.

## Decisions

* **Summarize reuses resident Qwen** with a bullet brief; no worker, no RAG.
* **Per-feature workers** via `?worker` imports, single `worker-client` helper, one-resident budget (load/unload on switch).
* **Quota gate** (1.25x) + consent before download; silent null on failure.
* **TTS Supertonic** (not SpeechT5) at fp16-equivalent; speaker embeddings via Cache API ArrayBuffer transfer.
* **TrOCR int8** (q4 missing); translation split as above.
* **Mirror fix** for `binary-mlc-llm-libs` (raw→jsDelivr, no doubled `/main`).
* **Chat freeze:** 100ms token batch, debounced persisted history (50/2s), rAF sticky scroll, weak-GPU guard.
* **Prod headers** `vercel.json` COOP `same-origin-allow-popups` + COEP `credentialless`; `vite.config.ts` exclude.

## Risks / Trade-offs

* 700MB+ total if all enabled — mitigated by on-demand + Wi-Fi pack.
* Low-resource Sesotho quality rough — expected for short tips, acceptable.
* TrOCR on a full screenshot returns noise — scoped to snippets.
