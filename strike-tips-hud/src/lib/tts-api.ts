/**
 * Client-side utilities for Gemini TTS and Groq Speech synthesis.
 */

export type TTSProvider = 'gemini' | 'groq' | 'offline';

export interface TTSVoiceProfile {
  id: string;
  name: string;
  provider: TTSProvider;
  gender: 'Female' | 'Male';
  description: string;
}

export const GEMINI_VOICES: TTSVoiceProfile[] = [
  { id: 'Kore', name: 'Kore', provider: 'gemini', gender: 'Female', description: 'Warm, natural & conversational tone' },
  { id: 'Puck', name: 'Puck', provider: 'gemini', gender: 'Male', description: 'Clear, balanced & friendly neutral voice' },
  { id: 'Charon', name: 'Charon', provider: 'gemini', gender: 'Male', description: 'Deep, calm authoritative baritone' },
  { id: 'Fenrir', name: 'Fenrir', provider: 'gemini', gender: 'Male', description: 'Crisp, confident race analyst' },
  { id: 'Zephyr', name: 'Zephyr', provider: 'gemini', gender: 'Female', description: 'Bright, energetic & upbeat voice' },
];

export const GROQ_VOICES: TTSVoiceProfile[] = [
  { id: 'autumn', name: 'Autumn', provider: 'groq', gender: 'Female', description: 'Expressive conversational narrator' },
  { id: 'diana', name: 'Diana', provider: 'groq', gender: 'Female', description: 'Crisp, articulate track announcer' },
  { id: 'hannah', name: 'Hannah', provider: 'groq', gender: 'Female', description: 'Warm, engaging broadcast host' },
  { id: 'austin', name: 'Austin', provider: 'groq', gender: 'Male', description: 'Dynamic, modern trackside radio' },
  { id: 'daniel', name: 'Daniel', provider: 'groq', gender: 'Male', description: 'Smooth, polished commentator' },
  { id: 'troy', name: 'Troy', provider: 'groq', gender: 'Male', description: 'Authoritative turf specialist' },
];

export const ALL_VOICES: TTSVoiceProfile[] = [...GEMINI_VOICES, ...GROQ_VOICES];

export interface SynthesizeOptions {
  text: string;
  provider?: TTSProvider;
  voice?: string;
  style?: string;
}

export interface SynthesizedAudioResult {
  blob: Blob;
  url: string;
  provider: string;
  voice: string;
  duration?: number;
}

// In-memory cache for synthesized audio blobs
const audioCache = new Map<string, SynthesizedAudioResult>();

export function getAudioCacheKey(options: SynthesizeOptions): string {
  return `${options.provider ?? 'gemini'}:${options.voice ?? 'default'}:${options.style ?? ''}:${options.text.trim()}`;
}

/**
 * Calls /api/tts to generate natural speech audio.
 */
export async function fetchSpeechAudio(options: SynthesizeOptions): Promise<SynthesizedAudioResult> {
  const clean = options.text.trim();
  if (!clean) throw new Error('Speech text cannot be empty');

  const cacheKey = getAudioCacheKey(options);
  const cached = audioCache.get(cacheKey);
  if (cached) return cached;

  const resp = await fetch('/api/tts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: clean,
      provider: options.provider ?? 'gemini',
      voice: options.voice,
      style: options.style,
    }),
  });

  if (!resp.ok) {
    let errMsg = `TTS request failed with status ${resp.status}`;
    try {
      const errJson = await resp.json();
      if (errJson.error) errMsg = errJson.error;
    } catch {}
    throw new Error(errMsg);
  }

  const effectiveProvider = resp.headers.get('X-TTS-Provider') || options.provider || 'gemini';
  const effectiveVoice = resp.headers.get('X-TTS-Voice') || options.voice || 'default';

  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);

  const result: SynthesizedAudioResult = {
    blob,
    url,
    provider: effectiveProvider,
    voice: effectiveVoice,
  };

  // Cache up to 40 recent utterances
  if (audioCache.size > 40) {
    const oldestKey = audioCache.keys().next().value;
    if (oldestKey) {
      const old = audioCache.get(oldestKey);
      if (old?.url) URL.revokeObjectURL(old.url);
      audioCache.delete(oldestKey);
    }
  }
  audioCache.set(cacheKey, result);

  return result;
}
