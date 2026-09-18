import { useCallback, useEffect, useRef, useState } from 'react';
import {
  TTSProvider,
  TTSVoiceProfile,
  GEMINI_VOICES,
  GROQ_VOICES,
  ALL_VOICES,
  fetchSpeechAudio,
  SynthesizeOptions,
} from '../lib/tts-api';

const VOICE_KEY = 'strike_tts_voice';
const PROVIDER_KEY = 'strike_tts_provider';

let activeAudio: HTMLAudioElement | null = null;

function stopActiveAudio() {
  if (activeAudio) {
    try {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    } catch {}
    activeAudio = null;
  }
}

export interface TTSState {
  provider: TTSProvider;
  setProvider: (provider: TTSProvider) => void;
  voiceId: string;
  setVoiceId: (id: string) => void;
  availableVoices: TTSVoiceProfile[];
  currentVoice: TTSVoiceProfile;
  cycleVoice: () => void;
  speaking: boolean;
  paused: boolean;
  busy: boolean;
  progress: number;
  progressText: string;
  deniedReason: string | null;
  modelSize: string;
  currentAudioUrl: string | null;
  playbackRate: number;
  setPlaybackRate: (rate: number) => void;
  speak: (text: string, options?: Partial<SynthesizeOptions>) => Promise<boolean>;
  pause: () => void;
  resume: () => void;
  stop: () => void;
}

export function useTTS(): TTSState {
  const [provider, setProviderState] = useState<TTSProvider>(() => {
    try {
      const saved = localStorage.getItem(PROVIDER_KEY);
      if (saved === 'gemini' || saved === 'groq') return saved;
    } catch {}
    return 'gemini';
  });

  const [voiceId, setVoiceIdState] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(VOICE_KEY);
      if (saved && ALL_VOICES.some((v) => v.id === saved)) return saved;
    } catch {}
    return 'Kore';
  });

  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const [deniedReason, setDeniedReason] = useState<string | null>(null);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [playbackRate, setPlaybackRateState] = useState(1.0);

  const providerRef = useRef(provider);
  providerRef.current = provider;
  const voiceRef = useRef(voiceId);
  voiceRef.current = voiceId;
  const rateRef = useRef(playbackRate);
  rateRef.current = playbackRate;

  const setProvider = useCallback((newProvider: TTSProvider) => {
    setProviderState(newProvider);
    try {
      localStorage.setItem(PROVIDER_KEY, newProvider);
    } catch {}

    // Pick appropriate default voice for new provider
    if (newProvider === 'gemini') {
      const fallback = 'Kore';
      if (!GEMINI_VOICES.some((v) => v.id === voiceRef.current)) {
        setVoiceIdState(fallback);
        try {
          localStorage.setItem(VOICE_KEY, fallback);
        } catch {}
      }
    } else if (newProvider === 'groq') {
      const fallback = 'autumn';
      if (!GROQ_VOICES.some((v) => v.id === voiceRef.current)) {
        setVoiceIdState(fallback);
        try {
          localStorage.setItem(VOICE_KEY, fallback);
        } catch {}
      }
    }
  }, []);

  const setVoiceId = useCallback((id: string) => {
    setVoiceIdState(id);
    try {
      localStorage.setItem(VOICE_KEY, id);
    } catch {}
  }, []);

  const availableVoices = provider === 'groq' ? GROQ_VOICES : GEMINI_VOICES;
  const currentVoice =
    availableVoices.find((v) => v.id === voiceId) ||
    ALL_VOICES.find((v) => v.id === voiceId) ||
    GEMINI_VOICES[0];

  const cycleVoice = useCallback(() => {
    const list = providerRef.current === 'groq' ? GROQ_VOICES : GEMINI_VOICES;
    const idx = list.findIndex((v) => v.id === voiceRef.current);
    const next = list[(idx + 1) % list.length];
    setVoiceId(next.id);
  }, [setVoiceId]);

  const setPlaybackRate = useCallback((rate: number) => {
    setPlaybackRateState(rate);
    if (activeAudio) {
      activeAudio.playbackRate = rate;
    }
  }, []);

  const stop = useCallback(() => {
    stopActiveAudio();
    setSpeaking(false);
    setPaused(false);
  }, []);

  const pause = useCallback(() => {
    if (activeAudio && !activeAudio.paused) {
      activeAudio.pause();
      setPaused(true);
    }
  }, []);

  const resume = useCallback(() => {
    if (activeAudio && activeAudio.paused) {
      activeAudio.play().catch(() => {});
      setPaused(false);
    }
  }, []);

  const speak = useCallback(
    async (text: string, options?: Partial<SynthesizeOptions>): Promise<boolean> => {
      const clean = (text ?? '').trim();
      if (!clean) return false;

      stop();
      setBusy(true);
      setProgress(0.2);
      setProgressText('Synthesizing natural voice…');
      setDeniedReason(null);

      try {
        const targetProvider = options?.provider || providerRef.current;
        const targetVoice = options?.voice || voiceRef.current;

        const result = await fetchSpeechAudio({
          text: clean,
          provider: targetProvider,
          voice: targetVoice,
          style: options?.style,
        });

        setProgress(0.8);
        setProgressText('Streaming audio…');
        setCurrentAudioUrl(result.url);

        const audio = new Audio(result.url);
        audio.playbackRate = rateRef.current;
        activeAudio = audio;

        audio.onplay = () => {
          setSpeaking(true);
          setPaused(false);
          setProgress(1.0);
          setProgressText('');
        };

        audio.onended = () => {
          if (activeAudio === audio) {
            activeAudio = null;
            setSpeaking(false);
            setPaused(false);
          }
        };

        audio.onerror = () => {
          setSpeaking(false);
          setPaused(false);
          setDeniedReason('Audio playback error.');
        };

        await audio.play();
        return true;
      } catch (err: any) {
        setDeniedReason(err.message || 'Failed to synthesize speech.');
        return false;
      } finally {
        setBusy(false);
      }
    },
    [stop]
  );

  useEffect(() => {
    return () => {
      stopActiveAudio();
    };
  }, []);

  return {
    provider,
    setProvider,
    voiceId: currentVoice.id,
    setVoiceId,
    availableVoices,
    currentVoice,
    cycleVoice,
    speaking,
    paused,
    busy,
    progress,
    progressText,
    deniedReason,
    modelSize: 'Cloud Neural 24kHz',
    currentAudioUrl,
    playbackRate,
    setPlaybackRate,
    speak,
    pause,
    resume,
    stop,
  };
}

export { GEMINI_VOICES, GROQ_VOICES, ALL_VOICES };
