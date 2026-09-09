import { getStorageEstimate } from './webllm';

/**
 * Registry of downloadable on-device models beyond the WebLLM chat LLMs.
 * Each entry states its honest one-time download cost so the UI can ask
 * before spending mobile data/storage. Weights live in Cache API/OPFS
 * after first download and work fully offline.
 */
export interface OfflineModelDef {
  id: string;
  label: string;
  hfModel: string;
  /** One-time download bytes (weights + tokenizer + headroom). */
  bytes: number;
  blurb: string;
}

export const OFFLINE_MODELS: Record<string, OfflineModelDef> = {
  sentiment: {
    id: 'sentiment',
    label: 'On-device sentiment',
    hfModel: 'Xenova/distilbert-base-uncased-finetuned-sst-2-english',
    bytes: 110 * 1024 * 1024,
    blurb: 'Scores news mood on your phone. ~110MB once, then offline.',
  },
  tts: {
    id: 'tts',
    label: 'Voice reader (SpeechT5)',
    hfModel: 'Xenova/speecht5_tts',
    bytes: 220 * 1024 * 1024,
    blurb: 'Reads verdicts aloud on-device. ~220MB once, then offline.',
  },
  trocr: {
    id: 'trocr',
    label: 'Form image reader (TrOCR)',
    hfModel: 'Xenova/trocr-small-printed',
    bytes: 140 * 1024 * 1024,
    blurb: 'Reads text off form images. ~140MB once, then offline.',
  },
  'mt-af': {
    id: 'mt-af',
    label: 'Afrikaans translation',
    hfModel: 'Xenova/opus-mt-en-af',
    bytes: 90 * 1024 * 1024,
    blurb: 'Translate tips to Afrikaans. ~90MB once, then offline.',
  },
  'mt-mul': {
    id: 'mt-mul',
    label: 'isiZulu + Sesotho translation',
    hfModel: 'Xenova/m2m100_418M',
    bytes: 230 * 1024 * 1024,
    blurb: 'One model for isiZulu and Sesotho. ~230MB once, then offline.',
  },
};

/** SpeechT5 speaker embeddings (tiny .bin files, fetched on first voice use). */
export const XVECTOR_BASE =
  'https://huggingface.co/datasets/Xenova/cmu-arctic-xvectors-extracted/resolve/main';

export interface TtsVoice {
  id: string;
  label: string;
  file: string;
}

export const TTS_VOICES: TtsVoice[] = [
  { id: 'slt', label: 'Voice 1 · Female', file: 'cmu_us_slt_arctic-wav-arctic_a0001.bin' },
  { id: 'bdl', label: 'Voice 2 · Male', file: 'cmu_us_bdl_arctic-wav-arctic_a0001.bin' },
  { id: 'clb', label: 'Voice 3 · Female', file: 'cmu_us_clb_arctic-wav-arctic_a0001.bin' },
];

export interface MtLang {
  id: 'af' | 'zu' | 'st';
  label: string;
  model: 'mt-af' | 'mt-mul';
  /** Target code passed to the model (m2m100 needs explicit langs). */
  tgt: string;
}

export const MT_LANGS: MtLang[] = [
  { id: 'af', label: 'Afrikaans', model: 'mt-af', tgt: 'af' },
  { id: 'zu', label: 'isiZulu', model: 'mt-mul', tgt: 'zu' },
  { id: 'st', label: 'Sesotho', model: 'mt-mul', tgt: 'st' },
];

export type OfflineModelId = keyof typeof OFFLINE_MODELS;

const CONSENT_KEY = 'strike_offline_models_enabled';

function readConsent(): string[] {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export function isModelEnabled(id: string): boolean {
  return readConsent().includes(id);
}

export function setModelEnabled(id: string, on: boolean): void {
  const next = readConsent().filter((x) => x !== id);
  if (on) next.push(id);
  try {
    localStorage.setItem(CONSENT_KEY, JSON.stringify(next));
  } catch {
    /* private mode: consent simply won't persist */
  }
}

export interface QuotaCheck {
  ok: boolean;
  reason?: string;
  freeMB?: number;
  needMB?: number;
}

/**
 * Quota gate shared by every on-device download. Requires 1.25x headroom
 * over the model's stated size. Never throws — returns a reason the UI
 * can render.
 */
export async function ensureStorageFor(id: OfflineModelId): Promise<QuotaCheck> {
  const def = OFFLINE_MODELS[id];
  if (!def) return { ok: false, reason: `Unknown model: ${id}` };
  const needMB = Math.ceil(def.bytes / (1024 * 1024));
  try {
    const est = await getStorageEstimate();
    if (!est.isSupported) {
      // Can't measure: allow the attempt, the worker will surface real errors.
      return { ok: true };
    }
    const freeMB = Math.floor(est.free / (1024 * 1024));
    const requiredMB = Math.ceil(needMB * 1.25);
    if (freeMB < requiredMB) {
      return {
        ok: false,
        reason: `Needs ~${requiredMB}MB free, only ~${freeMB}MB available. Free space or use Settings → Reset Browser AI Storage.`,
        freeMB,
        needMB: requiredMB,
      };
    }
    return { ok: true, freeMB, needMB: requiredMB };
  } catch {
    return { ok: true };
  }
}

export function formatMB(bytes: number): string {
  return `~${Math.ceil(bytes / (1024 * 1024))}MB`;
}
