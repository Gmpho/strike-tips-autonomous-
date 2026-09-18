import { GoogleGenAI, Modality } from '@google/genai';
import type { IncomingMessage, ServerResponse } from 'http';
import { pcmToWavBuffer, stitchWavBuffers } from './tts-service.ts';

export interface SwarmAgentDialogue {
  speaker: 'host' | 'analyst' | 'stats' | 'scout';
  speakerName: string;
  roleTitle: string;
  voice: 'Kore' | 'Puck' | 'Charon' | 'Fenrir' | 'Zephyr';
  avatar: string;
  text: string;
}

export interface PodcastEpisode {
  id: string;
  title: string;
  track: string;
  raceFocus: string;
  headline: string;
  durationEst: string;
  timestamp: string;
  dialogue: SwarmAgentDialogue[];
  summary: string[];
}

export interface GeneratePodcastRequest {
  track?: string;
  raceNumber?: string;
  topic?: string;
  runners?: Array<{ name: string; odds: string | number; edge?: number; form?: string }>;
}

const SWARM_ROSTER: Record<string, { name: string; title: string; voice: 'Kore' | 'Puck' | 'Charon' | 'Fenrir' | 'Zephyr'; avatar: string }> = {
  host: {
    name: 'Sipho Ndlovu',
    title: 'Lead Paddock Presenter',
    voice: 'Kore',
    avatar: '🎙️',
  },
  analyst: {
    name: 'Gareth Vance',
    title: 'Senior Form & Speed Analyst',
    voice: 'Charon',
    avatar: '🏇',
  },
  stats: {
    name: 'Dr. Elena Becker',
    title: 'Bayesian Edge & Kelly Modeler',
    voice: 'Zephyr',
    avatar: '📊',
  },
  scout: {
    name: 'Tebogo Molefe',
    title: 'Trackside Scout & Going Reporter',
    voice: 'Puck',
    avatar: '🔍',
  },
};

/**
 * Builds the AI podcast script featuring autonomous swarm discussion
 */
export async function generatePodcastScript(payload: GeneratePodcastRequest): Promise<PodcastEpisode> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is not configured on the server.');
  }

  const ai = new GoogleGenAI({ apiKey });
  const track = payload.track || 'Kenilworth';
  const raceNumber = payload.raceNumber || 'Race 7';
  const topic = payload.topic || 'Feature Value Edge & Exotic Bankroll Permutations';

  const runnersList = payload.runners && payload.runners.length > 0
    ? payload.runners.map(r => `- ${r.name}: Odds ${r.odds}${r.edge ? `, Edge ${r.edge}%` : ''}${r.form ? `, Form ${r.form}` : ''}`).join('\n')
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
{
  "title": "Short catchy episode title",
  "headline": "One sentence punchy summary",
  "summary": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"],
  "dialogue": [
    {
      "speaker": "host",
      "text": "..."
    },
    {
      "speaker": "analyst",
      "text": "..."
    }
  ]
}
Do not wrap in markdown quotes if possible, output raw JSON. Keep dialogue natural, trackside, and focused entirely on South African racing value.`;

  const response = await ai.models.generateContent({
    model: 'gemini-3.5-flash',
    contents: [{ parts: [{ text: prompt }] }],
    config: {
      temperature: 0.7,
      responseMimeType: 'application/json',
    },
  });

  const rawText = response.text || '{}';
  let parsed: any;
  try {
    parsed = JSON.parse(rawText);
  } catch {
    const clean = rawText.replace(/```json/g, '').replace(/```/g, '').trim();
    parsed = JSON.parse(clean);
  }

  const dialogue: SwarmAgentDialogue[] = (parsed.dialogue || []).map((turn: any) => {
    const roleKey = (turn.speaker || 'host').toLowerCase();
    const meta = SWARM_ROSTER[roleKey] || SWARM_ROSTER.host;
    return {
      speaker: roleKey as any,
      speakerName: meta.name,
      roleTitle: meta.title,
      voice: meta.voice,
      avatar: meta.avatar,
      text: turn.text || '',
    };
  });

  return {
    id: `pod-${Date.now()}`,
    title: parsed.title || `${track} ${raceNumber} Swarm Roundtable`,
    track,
    raceFocus: raceNumber,
    headline: parsed.headline || 'Autonomous racing agent consensus and value edge breakdown.',
    durationEst: `${Math.max(1, Math.round(dialogue.length * 0.4))}m ${((dialogue.length * 24) % 60)}s`,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    dialogue,
    summary: parsed.summary || [
      'Positive probability edge identified against market consensus',
      'Disciplined Half-Kelly bankroll allocation recommended',
      'Turf conditions favor early tactical speed from middle draws',
    ],
  };
}

/**
 * Synthesizes audio for a single dialogue line using Gemini TTS with assigned cast voice
 */
export async function synthesizePodcastLine(text: string, voice: string): Promise<Buffer> {
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
    model: 'gemini-2.5-flash-preview-tts',
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
 * Handles HTTP requests for the Autonomous Swarm Racing Podcast
 */
export async function handlePodcastRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const url = req.url || '';

  // GET /api/podcast/roster - Return cast roster
  if (req.method === 'GET' && (url === '/api/podcast/roster' || url.startsWith('/api/podcast/roster?'))) {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(SWARM_ROSTER));
    return;
  }

  // POST /api/podcast/generate - Generate fresh episode script
  if (req.method === 'POST' && (url === '/api/podcast/generate' || url.startsWith('/api/podcast/generate?'))) {
    let bodyStr = '';
    req.on('data', chunk => { bodyStr += chunk; });
    req.on('end', async () => {
      try {
        const body: GeneratePodcastRequest = JSON.parse(bodyStr || '{}');
        const episode = await generatePodcastScript(body);
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify(episode));
      } catch (err: any) {
        console.error('[Podcast Generate Error]', err);
        res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ error: err.message || 'Failed to generate podcast episode' }));
      }
    });
    return;
  }

  // POST /api/podcast/synthesize-line - Audio synthesize a single dialogue turn
  if (req.method === 'POST' && (url === '/api/podcast/synthesize-line' || url.startsWith('/api/podcast/synthesize-line?'))) {
    let bodyStr = '';
    req.on('data', chunk => { bodyStr += chunk; });
    req.on('end', async () => {
      try {
        const body = JSON.parse(bodyStr || '{}');
        const text = body.text;
        const voice = body.voice || 'Kore';
        if (!text) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Text is required' }));
          return;
        }
        const wavBuffer = await synthesizePodcastLine(text, voice);
        res.writeHead(200, {
          'Content-Type': 'audio/wav',
          'Content-Length': wavBuffer.length,
          'Access-Control-Allow-Origin': '*',
        });
        res.end(wavBuffer);
      } catch (err: any) {
        console.error('[Podcast Synth Line Error]', err);
        res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ error: err.message || 'Audio synthesis failed' }));
      }
    });
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not Found' }));
}
