import { pipeline, type TranslationPipeline } from '@huggingface/transformers';

// Opus-MT covers Afrikaans, m2m100 covers isiZulu, NLLB covers Sesotho.
// Pipes are cached per model id so switching languages doesn't reload.
const pipes = new Map<string, TranslationPipeline>();
const loading = new Map<string, Promise<void>>();

function loadModel(
  model: string,
  onProgress: (p: number, text: string) => void
): Promise<void> {
  if (pipes.has(model)) return Promise.resolve();
  const inflight = loading.get(model);
  if (inflight) return inflight;
  const p = (async () => {
    const pipe = await pipeline('translation', model, {
      dtype: 'q4',
      progress_callback: (r: any) => {
        onProgress(
          typeof r?.progress === 'number' ? r.progress / 100 : 0,
          String(r?.status ?? r?.text ?? 'loading')
        );
      },
    });
    pipes.set(model, pipe as TranslationPipeline);
  })()
    .catch((err) => {
      throw err;
    })
    .finally(() => {
      loading.delete(model);
    });
  loading.set(model, p);
  return p;
}

self.onmessage = async (e: MessageEvent) => {
  const { type, text, model, src_lang, tgt_lang, id } = e.data ?? {};
  const progress = (p: number, t: string) =>
    self.postMessage({ type: 'PROGRESS', id, progress: p, text: t });

  try {
    if (type === 'LOAD') {
      await loadModel(String(model), progress);
      self.postMessage({ type: 'READY', id });
      return;
    }
    if (type === 'TRANSLATE') {
      const input = String(text ?? '').slice(0, 1000).trim();
      if (!input) {
        self.postMessage({ type: 'RESULT', id, translation: '' });
        return;
      }
      const modelId = String(model);
      await loadModel(modelId, progress);
      const pipe = pipes.get(modelId)!;
      // m2m100/NLLB need explicit lang codes; Opus-MT is fixed
      // en->af and takes the text alone (extra options break it).
      const needsLangs = modelId.includes('m2m100') || modelId.includes('nllb');
      const out: any = needsLangs
        ? await pipe(input, { src_lang: String(src_lang || 'en'), tgt_lang: String(tgt_lang || 'zu') })
        : await pipe(input);
      const first = Array.isArray(out) ? out[0] : out;
      self.postMessage({ type: 'RESULT', id, translation: String(first?.translation_text ?? '') });
      return;
    }
    if (type === 'UNLOAD') {
      pipes.clear();
      loading.clear();
      self.postMessage({ type: 'UNLOADED', id });
    }
  } catch (err: any) {
    self.postMessage({ type: 'ERROR', id, error: String(err?.message ?? err) });
  }
};
