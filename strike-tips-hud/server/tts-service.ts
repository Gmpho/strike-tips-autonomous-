import { GoogleGenAI, Modality } from '@google/genai';
import type { IncomingMessage, ServerResponse } from 'http';

/**
 * Builds a standard 44-byte RIFF WAV header for linear 16-bit PCM audio.
 */
export function pcmToWavBuffer(pcmBytes: Uint8Array, sampleRate = 24000, numChannels = 1): Buffer {
  const byteRate = sampleRate * numChannels * 2;
  const blockAlign = numChannels * 2;
  const subChunk2Size = pcmBytes.length;
  const chunkSize = 36 + subChunk2Size;

  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(chunkSize, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16); // Subchunk1Size (16 for PCM)
  header.writeUInt16LE(1, 20);  // AudioFormat (1 = PCM)
  header.writeUInt16LE(numChannels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(16, 34); // BitsPerSample
  header.write('data', 36);
  header.writeUInt32LE(subChunk2Size, 40);

  return Buffer.concat([header, Buffer.from(pcmBytes)]);
}

/**
 * Splits text into segments under maxLen without breaking sentences in awkward places.
 * Groq Orpheus accepts max 200 characters per speech segment.
 */
export function splitTextForGroq(text: string, maxLen = 190): string[] {
  const clean = text.trim();
  if (clean.length <= maxLen) return [clean];

  const sentences = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [clean];
  const chunks: string[] = [];
  let current = '';

  for (const s of sentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;
    if ((current + ' ' + trimmed).trim().length <= maxLen) {
      current = (current + ' ' + trimmed).trim();
    } else {
      if (current) chunks.push(current);
      if (trimmed.length <= maxLen) {
        current = trimmed;
      } else {
        const words = trimmed.split(/\s+/);
        let sub = '';
        for (const w of words) {
          if ((sub + ' ' + w).trim().length <= maxLen) {
            sub = (sub + ' ' + w).trim();
          } else {
            if (sub) chunks.push(sub);
            sub = w;
          }
        }
        current = sub;
      }
    }
  }
  if (current) chunks.push(current);
  return chunks.length > 0 ? chunks : [clean.slice(0, maxLen)];
}

/**
 * Stitches multiple WAV audio buffers into a single seamless WAV file by preserving the
 * master header and merging PCM payloads.
 */
export function stitchWavBuffers(buffers: Buffer[]): Buffer {
  if (buffers.length === 0) return Buffer.alloc(0);
  if (buffers.length === 1) return buffers[0];
  const first = buffers[0];
  if (first.length < 44) return Buffer.concat(buffers);

  const pcmParts = buffers.map((b) => (b.length > 44 ? b.subarray(44) : b));
  const totalPcm = Buffer.concat(pcmParts);

  const header = Buffer.from(first.subarray(0, 44));
  header.writeUInt32LE(36 + totalPcm.length, 4);
  header.writeUInt32LE(totalPcm.length, 40);
  return Buffer.concat([header, totalPcm]);
}

/**
 * Synthesizes natural speech using Google Gemini TTS (gemini-3.1-flash-tts-preview).
 */
export async function synthesizeGeminiTTS(text: string, voice = 'Kore'): Promise<Buffer> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is not configured on the server.');
  }

  const ai = new GoogleGenAI({
    apiKey,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });

  const validVoices = ['Kore', 'Puck', 'Charon', 'Fenrir', 'Zephyr'];
  const voiceName = validVoices.includes(voice) ? voice : 'Kore';

  const response = await ai.models.generateContent({
    model: 'gemini-3.1-flash-tts-preview',
    contents: [{ parts: [{ text }] }],
    config: {
      responseModalities: [Modality.AUDIO],
      speechConfig: {
        voiceConfig: {
          prebuiltVoiceConfig: { voiceName },
        },
      },
    },
  });

  const b64 = response.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
  if (!b64) {
    throw new Error('No audio returned from Gemini TTS.');
  }

  const pcmBytes = Buffer.from(b64, 'base64');
  return pcmToWavBuffer(pcmBytes, 24000, 1);
}

/**
 * Synthesizes speech using the Groq Speech API (canopylabs/orpheus-v1-english).
 */
export async function synthesizeGroqTTS(
  text: string,
  voice = 'autumn',
  style?: string
): Promise<Buffer> {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error(
      'GROQ_API_KEY is not configured. Please supply a Groq API key in Settings > Secrets or use Gemini TTS.'
    );
  }

  const validVoices = ['autumn', 'diana', 'hannah', 'austin', 'daniel', 'troy'];
  const voiceName = validVoices.includes(voice) ? voice : 'autumn';

  // Apply vocal direction cue if requested (e.g., [cheerful], [whisper], [dramatic])
  let formattedText = text;
  if (style && !formattedText.startsWith('[')) {
    const cue = style.startsWith('[') ? style : `[${style}]`;
    formattedText = `${cue} ${formattedText}`;
  }

  const chunks = splitTextForGroq(formattedText, 190);
  const audioChunks: Buffer[] = [];

  for (const chunk of chunks) {
    const resp = await fetch('https://api.groq.com/openai/v1/audio/speech', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'canopylabs/orpheus-v1-english',
        input: chunk,
        voice: voiceName,
        response_format: 'wav',
      }),
    });

    if (!resp.ok) {
      const errBody = await resp.text();
      throw new Error(`Groq TTS API returned HTTP ${resp.status}: ${errBody}`);
    }

    const arrayBuf = await resp.arrayBuffer();
    audioChunks.push(Buffer.from(arrayBuf));
  }

  return stitchWavBuffers(audioChunks);
}

export const TTS_METADATA = {
  providers: {
    gemini: {
      name: 'Gemini Natural TTS',
      model: 'gemini-3.1-flash-tts-preview',
      available: Boolean(process.env.GEMINI_API_KEY),
      defaultVoice: 'Kore',
      voices: [
        { id: 'Kore', name: 'Kore', gender: 'Female', description: 'Warm, natural & conversational' },
        { id: 'Puck', name: 'Puck', gender: 'Male', description: 'Clear, balanced neutral tone' },
        { id: 'Charon', name: 'Charon', gender: 'Male', description: 'Deep, calm authoritative baritone' },
        { id: 'Fenrir', name: 'Fenrir', gender: 'Male', description: 'Crisp, confident race analyst' },
        { id: 'Zephyr', name: 'Zephyr', gender: 'Female', description: 'Bright, energetic & upbeat' },
      ],
    },
    groq: {
      name: 'Groq Orpheus Speech',
      model: 'canopylabs/orpheus-v1-english',
      available: Boolean(process.env.GROQ_API_KEY),
      defaultVoice: 'autumn',
      styles: ['cheerful', 'dramatic', 'whisper', 'calm', 'urgent'],
      voices: [
        { id: 'autumn', name: 'Autumn', gender: 'Female', description: 'Conversational track narrator' },
        { id: 'diana', name: 'Diana', gender: 'Female', description: 'Crisp, articulate announcer' },
        { id: 'hannah', name: 'Hannah', gender: 'Female', description: 'Warm, engaging broadcast host' },
        { id: 'austin', name: 'Austin', gender: 'Male', description: 'Dynamic, modern trackside radio' },
        { id: 'daniel', name: 'Daniel', gender: 'Male', description: 'Smooth, polished commentator' },
        { id: 'troy', name: 'Troy', gender: 'Male', description: 'Authoritative turf analyst' },
      ],
    },
  },
};

/**
 * Request handler for Vite dev server / Connect middleware.
 */
export async function handleTTSRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const url = req.url || '';

  // GET /api/tts/voices
  if (req.method === 'GET' && (url === '/api/tts/voices' || url.startsWith('/api/tts/voices?'))) {
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.end(JSON.stringify(TTS_METADATA));
    return;
  }

  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    res.statusCode = 204;
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-KEY');
    res.end();
    return;
  }

  if (req.method !== 'POST') {
    res.statusCode = 405;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ error: 'Method Not Allowed' }));
    return;
  }

  // Read request body
  const bodyChunks: Buffer[] = [];
  for await (const chunk of req) {
    bodyChunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk);
  }
  const bodyText = Buffer.concat(bodyChunks).toString('utf-8');

  let payload: { text?: string; provider?: string; voice?: string; style?: string } = {};
  try {
    payload = JSON.parse(bodyText);
  } catch {
    res.statusCode = 400;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ error: 'Invalid JSON body' }));
    return;
  }

  const rawText = (payload.text || '').trim();
  if (!rawText) {
    res.statusCode = 400;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ error: 'Text is required for text-to-speech conversion.' }));
    return;
  }

  const provider = (payload.provider || 'gemini').toLowerCase();
  const voice = payload.voice;
  const style = payload.style;

  try {
    let wavBuffer: Buffer;
    let effectiveProvider = provider;
    let effectiveVoice = voice;

    if (provider === 'groq') {
      if (!process.env.GROQ_API_KEY) {
        // Fallback gracefully to Gemini if Groq key isn't provided
        effectiveProvider = 'gemini';
        effectiveVoice = 'Kore';
        wavBuffer = await synthesizeGeminiTTS(rawText, 'Kore');
      } else {
        wavBuffer = await synthesizeGroqTTS(rawText, voice, style);
      }
    } else {
      effectiveProvider = 'gemini';
      wavBuffer = await synthesizeGeminiTTS(rawText, voice);
    }

    res.statusCode = 200;
    res.setHeader('Content-Type', 'audio/wav');
    res.setHeader('Content-Length', wavBuffer.length.toString());
    res.setHeader('X-TTS-Provider', effectiveProvider);
    res.setHeader('X-TTS-Voice', effectiveVoice || 'default');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Expose-Headers', 'X-TTS-Provider, X-TTS-Voice');
    res.end(wavBuffer);
  } catch (err: any) {
    res.statusCode = 500;
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.end(
      JSON.stringify({
        error: err.message || 'Speech synthesis failed.',
        provider,
      })
    );
  }
}
