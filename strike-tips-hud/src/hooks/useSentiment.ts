import { useCallback, useRef, useState } from 'react';
import {
  OFFLINE_MODELS,
  ensureStorageFor,
  formatMB,
  isModelEnabled,
  setModelEnabled,
} from '../lib/offline-models';
import { callWorker, getSharedWorker } from '../lib/worker-client';

export type SentimentLabel = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';

export interface SentimentResult {
  label: SentimentLabel;
  score: number;
}

// In-memory results per text (cap 200). Nothing persists: scores are cheap
// to recompute and news churns.
const cache = new Map<string, SentimentResult | null>();

function cacheKey(text: string): string {
  let h = 0;
  for (let i = 0; i < text.length; i++) {
    h = (Math.imul(31, h) + text.charCodeAt(i)) | 0;
  }
  return `${text.length}:${h}`;
}

export interface SentimentState {
  enabled: boolean;
  downloading: boolean;
  progress: number;
  progressText: string;
  deniedReason: string | null;
  modelSize: string;
  enable: () => Promise<boolean>;
  analyze: (text: string) => Promise<SentimentResult | null>;
}

/**
 * On-device sentiment for news text. Nothing renders until a result lands;
 * failures resolve null (silent).
 */
export function useSentiment(): SentimentState {
  const [enabled, setEnabled] = useState(() => isModelEnabled('sentiment'));
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [deniedReason, setDeniedReason] = useState<string | null>(null);
  const progressRef = useRef({ setProgress, setProgressText });
  progressRef.current = { setProgress, setProgressText };

  const boot = useCallback(async (): Promise<boolean> => {
    const w = await getSharedWorker(
      'sentiment',
      () => new URL('../workers/sentiment.worker.ts', import.meta.url),
      (p, t) => {
        progressRef.current.setProgress(p);
        progressRef.current.setProgressText(t);
      }
    );
    if (!w) return false;
    const msg = await callWorker<{ type: string }>(w, { type: 'LOAD' }, 10000);
    return !!msg && msg.type !== 'ERROR';
  }, []);

  const enable = useCallback(async (): Promise<boolean> => {
    const gate = await ensureStorageFor('sentiment');
    if (!gate.ok) {
      setDeniedReason(gate.reason ?? 'Not enough storage.');
      return false;
    }
    setDeniedReason(null);
    setModelEnabled('sentiment', true);
    setEnabled(true);
    setDownloading(true);
    try {
      await boot();
      return true;
    } finally {
      setDownloading(false);
    }
  }, [boot]);

  const analyze = useCallback(
    async (text: string): Promise<SentimentResult | null> => {
      const clean = (text ?? '').trim();
      if (!clean || !isModelEnabled('sentiment')) return null;
      const key = cacheKey(clean);
      if (cache.has(key)) return cache.get(key) ?? null;
      const gate = await ensureStorageFor('sentiment');
      if (!gate.ok) return null;
      const w = await getSharedWorker('sentiment', () =>
        new URL('../workers/sentiment.worker.ts', import.meta.url)
      );
      if (!w) return null;
      const msg = await callWorker<{ type: string; label?: string; score?: number }>(
        w,
        { type: 'ANALYZE', text: clean }
      );
      const result =
        msg && msg.type === 'RESULT'
          ? {
              label: (msg.label === 'POSITIVE' || msg.label === 'NEGATIVE' ? msg.label : 'NEUTRAL') as SentimentLabel,
              score: msg.score ?? 0,
            }
          : null;
      cache.set(key, result);
      while (cache.size > 200) {
        const first = cache.keys().next();
        if (first.done) break;
        cache.delete(first.value);
      }
      return result;
    },
    []
  );

  return {
    enabled,
    downloading,
    progress,
    progressText,
    deniedReason,
    modelSize: formatMB(OFFLINE_MODELS.sentiment.bytes),
    enable,
    analyze,
  };
}
