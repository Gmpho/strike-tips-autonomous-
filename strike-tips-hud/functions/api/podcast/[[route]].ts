// Pages Function: /api/podcast/* — Autonomous Swarm Racing Podcast.
// Production port of server/podcast-service.ts (dev-only vite plugin).
// Spend protection: 5 calls/min per IP (each synth burns a TTS call),
// 1000-char cap per synthesized line, roster is static (no key needed).

interface Env {
  GEMINI_API_KEY?: string;
}

interface SwarmAgentDialogue {
  speaker: 'host' | 'analyst' | 'stats' | 'scout';
  speakerName: string;
  roleTitle: string;
  voice: 'Kore' | 'Puck' | 'Charon' | 'Fenrir' | 'Zephyr';
  avatar: string;
  text: string;
}

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 5;
const MAX_SYNTH_CHARS = 1000;
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

const SWARM_ROSTER: Record<string, { name: string; title: string; voice: string; avatar: string }> = {
  host: { name: 'Sipho Ndlovu', title: 'Lead Paddock Presenter', voice: 'Kore', avatar: '🎙️' },
  analyst: { name: 'Gareth Vance', title: 'Senior Form & Speed Analyst', voice: 'Charon', avatar: '🏇' },
  stats: { name: 'Dr. Elena Becker', title: 'Bayesian Edge & Kelly Modeler', voice: 'Zephyr', avatar: '📊' },
  scout: { name: 'Tebogo Molefe', title: 'Trackside Scout & Going Reporter', voice: 'Puck', avatar: '🔍' },
};

/** 16-bit PCM bytes -> WAV bytes (Workers-safe, no Node Buffer). */
function pcmToWav(pcm: Uint8Array, sampleRate = 24000, numChannels = 1): Uint8Array {
  const header = new Uint8Array(44);
  const view = new DataView(header.buffer);
  const writeStr = (off: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + pcm.length, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * 2, true);
  view.setUint16(32, numChannels * 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, pcm.length, true);
  const out = new Uint8Array(44 + pcm.length);
  out.set(header, 0);
  out.set(pcm, 44);
  return out;
}

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

async function synthesizeLine(apiKey: string, text: string, voice: string): Promise<Uint8Array> {
  const validVoices = ['Kore', 'Puck', 'Charon', 'Fenrir', 'Zephyr'];
  const voiceName = validVoices.includes(voice) ? voice : 'Kore';
  const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: text.slice(0, MAX_SYNTH_CHARS) }] }],
      generationConfig: {
        responseModalities: ['AUDIO'],
        speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName } } },
      },
    }),
  });
  if (!resp.ok) throw new Error(`TTS error: ${await resp.text()}`);
  const data: any = await resp.json();
  const b64 = data.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
  if (!b64) throw new Error('No audio returned from Gemini TTS.');
  return pcmToWav(b64ToBytes(b64), 24000, 1);
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(url.origin) });
  }
  const path = url.pathname;

  if (request.method === 'GET' && path.endsWith('/roster')) {
    return Response.json(SWARM_ROSTER, { headers: corsHeaders(url.origin) });
  }

  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (hitRate(ip)) {
    return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { ...corsHeaders(url.origin), 'Retry-After': '60' } });
  }
  if (!env.GEMINI_API_KEY) {
    return Response.json({ error: 'GEMINI_API_KEY is not configured on the server.' }, { status: 400, headers: corsHeaders(url.origin) });
  }

  if (request.method === 'POST' && path.endsWith('/generate')) {
    try {
      const payload = await request.json() as any;
      const track = payload.track || 'Kenilworth';
      const raceNumber = payload.raceNumber || 'Race 7';
      const topic = payload.topic || 'Feature Value Edge & Exotic Bankroll Permutations';
      const runnersList = payload.runners?.length
        ? payload.runners.map((r: any) => `- ${r.name}: Odds ${r.odds}${r.edge ? `, Edge ${r.edge}%` : ''}${r.form ? `, Form ${r.form}` : ''}`).join('\n')
        : `- Firealley: Odds 4.2, Edge 8.4%, Form 1-2-1\n- Master Archie: Odds 6.5, Edge 6.1%, Form 3-1-4\n- Gimme A Prince: Odds 2.8, Market Favourite, Form 1-1-2\n- Silver Operator: Odds 14.0, Longshot Outsider, Form 5-4-3`;
      const prompt = `You are producing an episode of the "Strike Swarm Racing Podcast" — an autonomous, lively South African thoroughbred racing intelligence show.
Show Context:
- Track: ${track}
- Focus: ${raceNumber} (${topic})
- Key Contenders:
${runnersList}

The Swarm cast features 4 autonomous AI personalities:
1. "host" (Sipho Ndlovu): Energetic paddock anchor, moderates the discussion, frames the odds, keeps banter tight.
2. "analyst" (Gareth Vance): Veteran track analyst, studies draw bias, turn of foot, course geometry, and jockey strike rates.
3. "stats" (Dr. Elena Becker): Quantitative Bayesian modeler, talks probability edges, Half-Kelly bankroll exposure, market implied prices.
4. "scout" (Tebogo Molefe): Paddock scout reporting on the ground (going pen reading, sweat, pre-race parade demeanor, rail bias).

Write an exciting, crisp 6 to 8 turn podcast dialogue discussing value, threats, and banker selections.
Format your output as valid JSON matching this exact structure:
{"title": "Short catchy episode title", "headline": "One sentence punchy summary", "summary": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"], "dialogue": [{"speaker": "host", "text": "..."}, {"speaker": "analyst", "text": "..."}]}
Do not wrap in markdown quotes if possible, output raw JSON. Keep dialogue natural, trackside, and focused entirely on South African racing value.`;
      const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=${env.GEMINI_API_KEY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.7, maxOutputTokens: 2000, responseMimeType: 'application/json' },
        }),
      });
      if (!resp.ok) throw new Error(`Script error: ${await resp.text()}`);
      const data: any = await resp.json();
      const rawText: string = data.candidates?.[0]?.content?.parts?.map((p: any) => p.text || '').join('') || '{}';
      let parsed: any;
      try { parsed = JSON.parse(rawText); }
      catch { parsed = JSON.parse(rawText.replace(/```json/g, '').replace(/```/g, '').trim()); }
      const dialogue: SwarmAgentDialogue[] = (parsed.dialogue || []).slice(0, 10).map((turn: any) => {
        const roleKey = String(turn.speaker || 'host').toLowerCase();
        const meta = SWARM_ROSTER[roleKey] || SWARM_ROSTER.host;
        return { speaker: roleKey as any, speakerName: meta.name, roleTitle: meta.title, voice: meta.voice as any, avatar: meta.avatar, text: String(turn.text || '').slice(0, MAX_SYNTH_CHARS) };
      });
      return Response.json({
        id: `pod-${Date.now()}`,
        title: parsed.title || `${track} ${raceNumber} Swarm Roundtable`,
        track,
        raceFocus: raceNumber,
        headline: parsed.headline || 'Autonomous racing agent consensus and value edge breakdown.',
        durationEst: `${Math.max(1, Math.round(dialogue.length * 0.4))}m ${((dialogue.length * 24) % 60)}s`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        dialogue,
        summary: parsed.summary || ['Positive probability edge identified against market consensus', 'Disciplined Half-Kelly bankroll allocation recommended', 'Turf conditions favor early tactical speed from middle draws'],
      }, { headers: corsHeaders(url.origin) });
    } catch (err: any) {
      return Response.json({ error: err.message || 'Failed to generate podcast episode' }, { status: 500, headers: corsHeaders(url.origin) });
    }
  }

  if (request.method === 'POST' && path.endsWith('/synthesize-line')) {
    try {
      const body: any = await request.json();
      if (!body.text) {
        return Response.json({ error: 'Text is required' }, { status: 400, headers: corsHeaders(url.origin) });
      }
      const wav = await synthesizeLine(env.GEMINI_API_KEY, String(body.text), body.voice || 'Kore');
      return new Response(wav.buffer as ArrayBuffer, { headers: { 'Content-Type': 'audio/wav', 'Content-Length': String(wav.length), ...corsHeaders(url.origin) } });
    } catch (err: any) {
      return Response.json({ error: err.message || 'Audio synthesis failed' }, { status: 500, headers: corsHeaders(url.origin) });
    }
  }

  return Response.json({ error: 'Not Found' }, { status: 404, headers: corsHeaders(url.origin) });
};
