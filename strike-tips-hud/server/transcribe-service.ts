import { GoogleGenAI } from '@google/genai';
import type { IncomingMessage, ServerResponse } from 'http';

export interface TranscribeRequestPayload {
  audioBase64: string;
  mimeType?: string;
  provider?: 'gemini' | 'groq';
}

export async function handleTranscribeRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Method Not Allowed' }));
    return;
  }

  let bodyStr = '';
  req.on('data', chunk => {
    bodyStr += chunk;
  });

  req.on('end', async () => {
    try {
      const body: TranscribeRequestPayload = JSON.parse(bodyStr || '{}');
      if (!body.audioBase64) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing audioBase64 in request body' }));
        return;
      }

      const mimeType = body.mimeType || 'audio/webm';
      const provider = body.provider || 'gemini';

      // If Groq Whisper requested
      if (provider === 'groq') {
        const groqApiKey = process.env.GROQ_API_KEY;
        if (groqApiKey) {
          try {
            const transcription = await transcribeWithGroq(body.audioBase64, mimeType, groqApiKey);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ text: transcription, provider: 'groq', model: 'whisper-large-v3' }));
            return;
          } catch (groqErr: any) {
            console.warn('[Groq Whisper Failed, falling back to Gemini Transcribe]', groqErr.message);
          }
        }
      }

      // Default: gemini-3.5-transcribe
      const geminiApiKey = process.env.GEMINI_API_KEY;
      if (!geminiApiKey) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'GEMINI_API_KEY is not configured on the server.' }));
        return;
      }

      const ai = new GoogleGenAI({ apiKey: geminiApiKey });
      const cleanBase64 = body.audioBase64.replace(/^data:[^;]+;base64,/, '');

      const response = await ai.models.generateContent({
        model: 'gemini-3.5-transcribe',
        contents: [
          {
            inlineData: {
              data: cleanBase64,
              mimeType,
            },
          },
          'Transcribe the speech in this audio query verbatim. Output only the transcribed text with no explanations or metadata.',
        ],
      });

      const text = (response.text || '').trim();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ text, provider: 'gemini', model: 'gemini-3.5-transcribe' }));
    } catch (err: any) {
      console.error('[Transcribe Service Error]', err);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message || 'Transcription failed' }));
      }
    }
  });
}

async function transcribeWithGroq(audioBase64: string, mimeType: string, apiKey: string): Promise<string> {
  const cleanBase64 = audioBase64.replace(/^data:[^;]+;base64,/, '');
  const buffer = Buffer.from(cleanBase64, 'base64');
  const ext = mimeType.includes('wav') ? 'wav' : mimeType.includes('mp4') ? 'mp4' : 'webm';

  const formData = new FormData();
  const blob = new Blob([buffer], { type: mimeType });
  formData.append('file', blob, `recording.${ext}`);
  formData.append('model', 'whisper-large-v3');
  formData.append('language', 'en');

  const response = await fetch('https://api.groq.com/openai/v1/audio/transcriptions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Groq Whisper error (${response.status}): ${errText}`);
  }

  const data: any = await response.json();
  return data.text || '';
}
