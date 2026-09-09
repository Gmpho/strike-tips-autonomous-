import { pipeline, type TextClassificationPipeline } from '@huggingface/transformers';

const MODEL_ID = 'Xenova/distilbert-base-uncased-finetuned-sst-2-english';
// DistilBERT caps at 512 tokens; char-truncate well under that.
const MAX_CHARS = 1200;

let classifier: TextClassificationPipeline | null = null;
let loadPromise: Promise<void> | null = null;

function loadClassifier(onProgress: (p: number, text: string) => void): Promise<void> {
  if (classifier) return Promise.resolve();
  if (!loadPromise) {
    loadPromise = (async () => {
      const pipe = await pipeline('sentiment-analysis', MODEL_ID, {
        // q4 keeps the one-time download phone-sized (~90MB); SST-2 sentiment
        // is unaffected by the quantization at this task difficulty.
        dtype: 'q4',
        progress_callback: (p: any) => {
          onProgress(
            typeof p?.progress === 'number' ? p.progress / 100 : 0,
            String(p?.status ?? p?.text ?? 'loading')
          );
        },
      });
      classifier = pipe as TextClassificationPipeline;
    })().catch((err) => {
      loadPromise = null;
      throw err;
    });
  }
  return loadPromise;
}

self.onmessage = async (e: MessageEvent) => {
  const { type, text, id } = e.data ?? {};
  const progress = (p: number, t: string) =>
    self.postMessage({ type: 'PROGRESS', id, progress: p, text: t });

  try {
    if (type === 'LOAD') {
      await loadClassifier(progress);
      self.postMessage({ type: 'READY', id });
      return;
    }
    if (type === 'ANALYZE') {
      const input = String(text ?? '').slice(0, MAX_CHARS).trim();
      if (!input) {
        self.postMessage({ type: 'RESULT', id, label: 'NEUTRAL', score: 0 });
        return;
      }
      await loadClassifier(progress);
      const out = (await classifier!(input)) as Array<{ label: string; score: number }>;
      const top = Array.isArray(out) ? out[0] : null;
      if (!top) {
        self.postMessage({ type: 'RESULT', id, label: 'NEUTRAL', score: 0 });
        return;
      }
      const label = top.label === 'POSITIVE' ? 'POSITIVE' : top.label === 'NEGATIVE' ? 'NEGATIVE' : 'NEUTRAL';
      self.postMessage({ type: 'RESULT', id, label, score: top.score ?? 0 });
      return;
    }
    if (type === 'UNLOAD') {
      classifier = null;
      loadPromise = null;
      self.postMessage({ type: 'UNLOADED', id });
    }
  } catch (err: any) {
    self.postMessage({ type: 'ERROR', id, error: String(err?.message ?? err) });
  }
};
