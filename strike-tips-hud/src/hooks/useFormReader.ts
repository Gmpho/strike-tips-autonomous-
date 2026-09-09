import { useCallback, useRef, useState } from 'react';
import {
  OFFLINE_MODELS,
  ensureStorageFor,
  formatMB,
  isModelEnabled,
  setModelEnabled,
} from '../lib/offline-models';
import { callWorker, getSharedWorker } from '../lib/worker-client';
import TrocrWorker from '../workers/trocr.worker.ts?worker';

export interface FormReaderState {
  reading: boolean;
  progress: number;
  progressText: string;
  deniedReason: string | null;
  modelSize: string;
  readImage: (image: Blob) => Promise<string | null>;
}

/**
 * Reads printed text off form/racecard images (TrOCR, on-device).
 * Scoped to snippets — full-page layout parsing is out of scope.
 * Explicit attach = consent; the quota gate still applies.
 */
export function useFormReader(): FormReaderState {
  const [reading, setReading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [deniedReason, setDeniedReason] = useState<string | null>(null);
  const progressRef = useRef({ setProgress, setProgressText });
  progressRef.current = { setProgress, setProgressText };

  const readImage = useCallback(async (image: Blob): Promise<string | null> => {
    const gate = await ensureStorageFor('trocr');
    if (!gate.ok) {
      setDeniedReason(gate.reason ?? 'Not enough storage.');
      return null;
    }
    setDeniedReason(null);
    if (!isModelEnabled('trocr')) setModelEnabled('trocr', true);
    setReading(true);
    try {
      const w = await getSharedWorker('trocr', () => new TrocrWorker(), (p, t) => {
        progressRef.current.setProgress(p);
        progressRef.current.setProgressText(t);
      });
      if (!w) return null;
      const msg = await callWorker<{ type: string; text?: string }>(
        w,
        { type: 'READ', image },
        120000
      );
      const out = msg && msg.type === 'RESULT' ? (msg.text ?? '').trim() : null;
      return out ? out : null;
    } finally {
      setReading(false);
    }
  }, []);

  return {
    reading,
    progress,
    progressText,
    deniedReason,
    modelSize: formatMB(OFFLINE_MODELS.trocr.bytes),
    readImage,
  };
}
