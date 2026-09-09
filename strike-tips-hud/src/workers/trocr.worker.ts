import { pipeline, RawImage, type ImageToTextPipeline } from '@huggingface/transformers';

const MODEL_ID = 'Xenova/trocr-small-printed';

let reader: ImageToTextPipeline | null = null;
let loadPromise: Promise<void> | null = null;

function loadReader(onProgress: (p: number, text: string) => void): Promise<void> {
  if (reader) return Promise.resolve();
  if (!loadPromise) {
    loadPromise = (async () => {
      const pipe = await pipeline('image-to-text', MODEL_ID, {
        dtype: 'q4',
        progress_callback: (p: any) => {
          onProgress(
            typeof p?.progress === 'number' ? p.progress / 100 : 0,
            String(p?.status ?? p?.text ?? 'loading')
          );
        },
      });
      reader = pipe as ImageToTextPipeline;
    })().catch((err) => {
      loadPromise = null;
      throw err;
    });
  }
  return loadPromise;
}

self.onmessage = async (e: MessageEvent) => {
  const { type, image, id } = e.data ?? {};
  const progress = (p: number, t: string) =>
    self.postMessage({ type: 'PROGRESS', id, progress: p, text: t });

  try {
    if (type === 'LOAD') {
      await loadReader(progress);
      self.postMessage({ type: 'READY', id });
      return;
    }
    if (type === 'READ') {
      if (!(image instanceof Blob)) throw new Error('No image provided');
      await loadReader(progress);
      const img = await RawImage.fromBlob(image);
      const out: any = await reader!(img);
      const first = Array.isArray(out) ? out[0] : out;
      self.postMessage({ type: 'RESULT', id, text: String(first?.generated_text ?? '').trim() });
      return;
    }
    if (type === 'UNLOAD') {
      reader = null;
      loadPromise = null;
      self.postMessage({ type: 'UNLOADED', id });
    }
  } catch (err: any) {
    self.postMessage({ type: 'ERROR', id, error: String(err?.message ?? err) });
  }
};
