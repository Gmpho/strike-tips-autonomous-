import { useCallback, useRef, useState } from 'react';
import {
  MT_LANGS,
  OFFLINE_MODELS,
  ensureStorageFor,
  formatMB,
  isModelEnabled,
  setModelEnabled,
  type MtLang,
} from '../lib/offline-models';
import { callWorker, getSharedWorker } from '../lib/worker-client';
import TranslateWorker from '../workers/translate.worker.ts?worker';

// In-memory translations per (lang, text). News/tips churn; recompute is cheap.
const cache = new Map<string, string | null>();

export interface TranslationState {
  langId: MtLang['id'];
  setLangId: (id: MtLang['id']) => void;
  langs: typeof MT_LANGS;
  translating: boolean;
  progress: number;
  progressText: string;
  deniedReason: string | null;
  modelSize: string;
  translate: (text: string) => Promise<string | null>;
}

const LANG_KEY = 'strike_mt_lang';

/**
 * Outward translation of tips/verdicts (EN → AF/ZU/ST). Explicit tap =
 * consent; the quota gate still applies. Failures resolve null (silent).
 */
export function useTranslation(): TranslationState {
  const [langId, setLangIdState] = useState<MtLang['id']>(() => {
    try {
      const v = localStorage.getItem(LANG_KEY);
      return v === 'zu' || v === 'st' ? v : 'af';
    } catch {
      return 'af';
    }
  });
  const [translating, setTranslating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [deniedReason, setDeniedReason] = useState<string | null>(null);
  const langRef = useRef(langId);
  langRef.current = langId;
  const progressRef = useRef({ setProgress, setProgressText });
  progressRef.current = { setProgress, setProgressText };

  const setLangId = useCallback((id: MtLang['id']) => {
    langRef.current = id;
    try {
      localStorage.setItem(LANG_KEY, id);
    } catch {}
    setLangIdState(id);
  }, []);

  const translate = useCallback(async (text: string): Promise<string | null> => {
    const clean = (text ?? '').trim();
    if (!clean) return null;
    const lang = MT_LANGS.find((l) => l.id === langRef.current) ?? MT_LANGS[0];
    const key = `${lang.id}:${clean.length}:${clean.slice(0, 200)}`;
    if (cache.has(key)) return cache.get(key) ?? null;
    const gate = await ensureStorageFor(lang.model);
    if (!gate.ok) {
      setDeniedReason(gate.reason ?? 'Not enough storage.');
      return null;
    }
    setDeniedReason(null);
    if (!isModelEnabled(lang.model)) setModelEnabled(lang.model, true);
    setTranslating(true);
    try {
      const w = await getSharedWorker('translate', () => new TranslateWorker(), (p, t) => {
        progressRef.current.setProgress(p);
        progressRef.current.setProgressText(t);
      });
      if (!w) return null;
      const msg = await callWorker<{ type: string; translation?: string }>(
        w,
        {
          type: 'TRANSLATE',
          text: clean,
          model: OFFLINE_MODELS[lang.model].hfModel,
          src_lang: lang.src,
          tgt_lang: lang.tgt,
        },
        120000
      );
      const out = msg && msg.type === 'RESULT' ? (msg.translation ?? '').trim() : null;
      const result = out ? out : null;
      cache.set(key, result);
      while (cache.size > 100) {
        const first = cache.keys().next();
        if (first.done) break;
        cache.delete(first.value);
      }
      return result;
    } finally {
      setTranslating(false);
    }
  }, []);

  const lang = MT_LANGS.find((l) => l.id === langId) ?? MT_LANGS[0];

  return {
    langId,
    setLangId,
    langs: MT_LANGS,
    translating,
    progress,
    progressText,
    deniedReason,
    modelSize: formatMB(OFFLINE_MODELS[lang.model].bytes),
    translate,
  };
}
