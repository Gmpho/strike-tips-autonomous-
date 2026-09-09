import {
  OFFLINE_MODELS,
  ensureStorageFor,
  isModelEnabled,
  setModelEnabled,
  type OfflineModelId,
} from './offline-models';
import { callWorker, dropSharedWorker, getSharedWorker } from './worker-client';
import SentimentWorker from '../workers/sentiment.worker.ts?worker';
import TtsWorker from '../workers/tts.worker.ts?worker';
import TrocrWorker from '../workers/trocr.worker.ts?worker';
import TranslateWorker from '../workers/translate.worker.ts?worker';

export interface PackProgress {
  done: number;
  total: number;
  label: string;
  detail: string;
}

function makeWorkerFor(id: string): () => Worker {
  // Static constructors only — Vite must resolve worker chunks at build time.
  switch (id) {
    case 'sentiment':
      return () => new SentimentWorker();
    case 'tts':
      return () => new TtsWorker();
    case 'trocr':
      return () => new TrocrWorker();
    case 'mt-af':
    case 'mt-mul':
      return () => new TranslateWorker();
    default:
      throw new Error(`No worker for offline model: ${id}`);
  }
}

function loadMessage(id: string): Record<string, unknown> {
  if (id === 'mt-af' || id === 'mt-mul') {
    return { type: 'LOAD', model: OFFLINE_MODELS[id].hfModel };
  }
  return { type: 'LOAD' };
}

/**
 * Wi-Fi offline pack: downloads every listed model sequentially with
 * progress, then TERMINATES each worker so nothing lingers in RAM/VRAM.
 * Weights stay in Cache API/OPFS — later feature use loads from cache.
 * Failing models are reported, never fatal to the rest of the pack.
 */
export async function downloadPack(
  ids: OfflineModelId[],
  onProgress: (p: PackProgress) => void,
  isCancelled: () => boolean
): Promise<{ ok: boolean; failed: string[] }> {
  const failed: string[] = [];
  let done = 0;
  for (const id of ids) {
    if (isCancelled()) break;
    const def = OFFLINE_MODELS[id];
    if (!def) {
      done++;
      continue;
    }
    onProgress({ done, total: ids.length, label: def.label, detail: 'checking storage…' });
    const gate = await ensureStorageFor(id);
    if (!gate.ok) {
      failed.push(id);
      done++;
      onProgress({ done, total: ids.length, label: def.label, detail: gate.reason ?? 'denied' });
      continue;
    }
    if (!isModelEnabled(id)) setModelEnabled(id, true);
    try {
      const w = await getSharedWorker(id, makeWorkerFor(id), (p, t) =>
        onProgress({
          done,
          total: ids.length,
          label: def.label,
          detail: `${Math.round(p * 100)}% ${t}`,
        })
      );
      if (!w) {
        failed.push(id);
      } else {
        const msg = await callWorker<{ type: string }>(w, loadMessage(id), 600000);
        if (!msg || msg.type === 'ERROR') failed.push(id);
      }
    } catch {
      failed.push(id);
    } finally {
      dropSharedWorker(id);
    }
    done++;
    onProgress({ done, total: ids.length, label: def.label, detail: 'done' });
  }
  return { ok: failed.length === 0, failed };
}
