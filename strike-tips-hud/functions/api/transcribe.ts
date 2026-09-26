// Pages Function: POST /api/transcribe — speech-to-text (Groq Whisper → Gemini).
// Production port of server/transcribe-service.ts (dev-only vite plugin).
// Spend protection: 10 calls/min per IP + 8MB audio cap.

interface Env {
  GEMINI_API_KEY?: string;
  GROQ_API_KEY?: string;
}

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 10;
const MAX_AUDIO_BYTES = 8 * 1024 * 1024;
const rateStore = new Map<string, { count: number; resetAt: number }>();

function hitRate(ip: string): boolean {
  const now = Date.now();
  const entry = rateStore.get(ip);
  if (!entry || now > entry.resetAt) {
    rateStore.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return false;
  }
  entry.count++;
  return entry.count > RATE_MAX;
}

function corsHeaders(origin: string): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-API-KEY, Authorization',
    'Access-Control-Max-Age': '86400',
  };
}

function b64ToBytes(cleanBase64: string): Uint8Array {
  const bin = atob(cleanBase64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function transcribeWithGroq(audioBase64: string, mimeType: string, apiKey: string): Promise<string> {
  const clean = audioBase64.replace(/^data:[^;]+;base64,/, '');
  const bytes = b64ToBytes(clean);
  const ext = mimeType.includes('wav') ? 'wav' : mimeType.includes('mp4') ? 'mp4' : 'webm';
  const formData = new FormData();
  formData.append('file', new Blob([bytes.buffer as ArrayBuffer], { type: mimeType }), `recording.${ext}`);
  formData.append('model', 'whisper-large-v3');
  formData.append('language', 'en');
  const response = await fetch('https://api.groq.com/openai/v1/audio/transcriptions', {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}` },
    body: formData,
  });
  if (!response.ok) throw new Error(`Groq Whisper error (${response.status}): ${await response.text()}`);
  const data: any = await response.json();
  return data.text || '';
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(url.origin) });
  }
  if (request.method !== 'POST') {
    return Response.json({ error: 'Method Not Allowed' }, { status: 405, headers: corsHeaders(url.origin) });
  }
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (hitRate(ip)) {
    return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { ...corsHeaders(url.origin), 'Retry-After': '60' } });
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: 'Invalid JSON' }, { status: 400, headers: corsHeaders(url.origin) });
  }
  const audioBase64: string = body.audioBase64 || '';
  if (!audioBase64) {
    return Response.json({ error: 'Missing audioBase64 in request body' }, { status: 400, headers: corsHeaders(url.origin) });
  }
  const cleanLen = audioBase64.replace(/^data:[^;]+;base64,/, '').length;
  if (cleanLen * 0.75 > MAX_AUDIO_BYTES) {
    return Response.json({ error: 'Audio too large (8MB max)' }, { status: 413, headers: corsHeaders(url.origin) });
  }
  const mimeType = body.mimeType || 'audio/webm';
  const provider = body.provider || 'gemini';

  if (provider === 'groq' && env.GROQ_API_KEY) {
    try {
      const text = await transcribeWithGroq(audioBase64, mimeType, env.GROQ_API_KEY);
      return Response.json({ text, provider: 'groq', model: 'whisper-large-v3' }, { headers: corsHeaders(url.origin) });
    } catch (e: any) {
      // fall through to Gemini
    }
  }

  if (!env.GEMINI_API_KEY) {
    return Response.json({ error: 'GEMINI_API_KEY is not configured on the server.' }, { status: 400, headers: corsHeaders(url.origin) });
  }
  const clean = audioBase64.replace(/^data:[^;]+;base64,/, '');
  const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${env.GEMINI_API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{
        parts: [
          { inlineData: { data: clean, mimeType } },
          { text: 'Transcribe the speech in this audio query verbatim. Output only the transcribed text with no explanations or metadata.' },
        ],
      }],
      generationConfig: { maxOutputTokens: 500, temperature: 0 },
    }),
  });
  if (!resp.ok) {
    return Response.json({ error: `Transcription failed: ${await resp.text()}` }, { status: resp.status, headers: corsHeaders(url.origin) });
  }
  const data: any = await resp.json();
  const text = (data.candidates?.[0]?.content?.parts?.map((p: any) => p.text || '').join('') || '').trim();
  return Response.json({ text, provider: 'gemini', model: 'gemini-2.5-flash' }, { headers: corsHeaders(url.origin) });
};
