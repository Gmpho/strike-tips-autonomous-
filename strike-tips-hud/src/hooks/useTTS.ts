import { useCallback, useEffect, useRef, useState } from 'react';
import {
  OFFLINE_MODELS,
  TTS_VOICES,
  XVECTOR_BASE,
  ensureStorageFor,
  formatMB,
  isModelEnabled,
  setModelEnabled,
} from '../lib/offline-models';
import { callWorker, getSharedWorker } from '../lib/worker-client';

const VOICE_KEY = 'strike_tts_voice';
const VOICE_CACHE = 'tts-voices';

// In-memory voice bytes (copies are transferred to the worker per utterance).
const voiceMem = new Map<string, ArrayBuffer>();

let audioCtx: AudioContext | null = null;
let activeSource: AudioBufferSourceNode | null = null;

function stopPlayback() {
  try {
    activeSource?.stop();
  } catch {}
  activeSource = null;
}

/** Voice embedding bytes with Cache API persistence so voices work fully
 * offline. Memory first, Cache API second, network last (then cached). */
async function voiceBytes(file: string): Promise<ArrayBuffer | null> {
  const mem = voiceMem.get(file);
  if (mem) return mem.slice(0);
  const url = `${XVECTOR_BASE}/${file}`;
  try {
    if ('caches' in window) {
      const cache = await window.caches.open(VOICE_CACHE);
      let res = await cache.match(url);
      if (!res) {
        const fresh = await fetch(url);
        if (!fresh.ok) return null;
        await cache.put(url, fresh.clone());
        res = await cache.match(url);
      }
      if (res) {
        const buf = await res.arrayBuffer();
        if (buf.byteLength === 512 * 4) {
          voiceMem.set(file, buf);
          return buf.slice(0);
        }
        return null;
      }
    } else {
      const res = await fetch(url);
      if (!res.ok) return null;
      return await res.arrayBuffer();
    }
  } catch {
    return null;
  }
  return null;
}

export interface TTSState {
  voiceId: string;
  cycleVoice: () => void;
  speaking: boolean;
  busy: boolean;
  progress: number;
  progressText: string;
  deniedReason: string | null;
  modelSize: string;
  speak: (text: string) => Promise<boolean>;
  stop: () => void;
}

/**
 * On-device speech for verdicts. Explicit tap = consent; the quota gate
 * still applies. Playback stops any in-flight utterance first.
 */
export function useTTS(): TTSState {
  const [voiceId, setVoiceId] = useState(() => {
    try {
      return localStorage.getItem(VOICE_KEY) || TTS_VOICES[0].id;
    } catch {
      return TTS_VOICES[0].id;
    }
  });
  const [speaking, setSpeaking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [deniedReason, setDeniedReason] = useState<string | null>(null);
  const voiceRef = useRef(voiceId);
  voiceRef.current = voiceId;

  const cycleVoice = useCallback(() => {
    const idx = TTS_VOICES.findIndex((v) => v.id === voiceRef.current);
    const next = TTS_VOICES[(idx + 1) % TTS_VOICES.length];
    voiceRef.current = next.id;
    try {
      localStorage.setItem(VOICE_KEY, next.id);
    } catch {}
    setVoiceId(next.id);
  }, []);

  const stop = useCallback(() => {
    stopPlayback();
    setSpeaking(false);
  }, []);

  const speak = useCallback(async (text: string): Promise<boolean> => {
    const clean = (text ?? '').trim();
    if (!clean) return false;
    stopPlayback();
    const gate = await ensureStorageFor('tts');
    if (!gate.ok) {
      setDeniedReason(gate.reason ?? 'Not enough storage.');
      return false;
    }
    setDeniedReason(null);
    if (!isModelEnabled('tts')) setModelEnabled('tts', true);
    setBusy(true);
    try {
      const w = await getSharedWorker(
        'tts',
        () => new URL('../workers/tts.worker.ts', import.meta.url),
        (p, t) => {
          setProgress(p);
          setProgressText(t);
        }
      );
      if (!w) return false;
      const voice = TTS_VOICES.find((v) => v.id === voiceRef.current) ?? TTS_VOICES[0];
      const bytes = await voiceBytes(voice.file);
      if (!bytes) return false;
      const msg = await callWorker<{
        type: string;
        audio?: ArrayBuffer;
        samplingRate?: number;
        error?: string;
      }>(w, { type: 'SPEAK', text: clean, voiceData: bytes }, 120000, [bytes]);
      if (!msg || msg.type !== 'RESULT' || !msg.audio) return false;
      if (!audioCtx) audioCtx = new AudioContext();
      if (audioCtx.state === 'suspended') await audioCtx.resume();
      const rate = msg.samplingRate ?? 16000;
      const buf = audioCtx.createBuffer(1, msg.audio.byteLength / 4, rate);
      buf.copyToChannel(new Float32Array(msg.audio), 0);
      const src = audioCtx.createBufferSource();
      src.buffer = buf;
      src.connect(audioCtx.destination);
      activeSource = src;
      setSpeaking(true);
      src.onended = () => {
        if (activeSource === src) {
          activeSource = null;
          setSpeaking(false);
        }
      };
      src.start();
      return true;
    } catch {
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      stopPlayback();
    };
  }, []);

  const voice = TTS_VOICES.find((v) => v.id === voiceId) ?? TTS_VOICES[0];

  return {
    voiceId: voice.id,
    cycleVoice,
    speaking,
    busy,
    progress,
    progressText,
    deniedReason,
    modelSize: formatMB(OFFLINE_MODELS.tts.bytes),
    speak,
    stop,
  };
}

export { TTS_VOICES };
