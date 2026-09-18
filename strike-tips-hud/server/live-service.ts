import { GoogleGenAI, LiveServerMessage, Modality } from '@google/genai';
import type { WebSocketServer, WebSocket } from 'ws';

const LIVE_SYSTEM_INSTRUCTION = `You are Strike Tips Live Racing Agent, an interactive voice assistant for South African horse racing.
- Speak in natural, concise, clear conversational sentences suitable for speech audio.
- Guide users on upcoming races, runners, form, track conditions, odds value, and bankroll staking.
- Keep spoken answers brief, punchy, and professional (avoid reading long tables aloud).`;

export function setupLiveWebSocketServer(wss: WebSocketServer): void {
  wss.on('connection', async (clientWs: WebSocket) => {
    console.log('[Live WebSocket] Client connected');
    const geminiApiKey = process.env.GEMINI_API_KEY;

    if (!geminiApiKey) {
      clientWs.send(JSON.stringify({ error: 'GEMINI_API_KEY not configured on server.' }));
      clientWs.close();
      return;
    }

    let session: any = null;

    try {
      const ai = new GoogleGenAI({ apiKey: geminiApiKey });

      session = await ai.live.connect({
        model: 'gemini-3.8-live',
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: {
            voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } },
          },
          systemInstruction: LIVE_SYSTEM_INSTRUCTION,
        },
        callbacks: {
          onmessage: (message: LiveServerMessage) => {
            try {
              if (clientWs.readyState !== clientWs.OPEN) return;

              const parts = message.serverContent?.modelTurn?.parts || [];
              for (const part of parts) {
                if (part.inlineData?.data) {
                  clientWs.send(JSON.stringify({ audio: part.inlineData.data }));
                }
                if (part.text) {
                  clientWs.send(JSON.stringify({ text: part.text }));
                }
              }

              if (message.serverContent?.interrupted) {
                clientWs.send(JSON.stringify({ interrupted: true }));
              }
            } catch (msgErr) {
              console.warn('[Live Message Send Error]', msgErr);
            }
          },
          onerror: (err: any) => {
            console.error('[Live Session Error]', err);
            if (clientWs.readyState === clientWs.OPEN) {
              clientWs.send(JSON.stringify({ error: err.message || 'Live session error' }));
            }
          },
          onclose: () => {
            console.log('[Live Session Closed by Gemini]');
            if (clientWs.readyState === clientWs.OPEN) {
              clientWs.send(JSON.stringify({ closed: true }));
            }
          },
        },
      });

      clientWs.send(JSON.stringify({ ready: true, model: 'gemini-3.8-live' }));
    } catch (connErr: any) {
      console.error('[Failed to connect to Gemini Live]', connErr);
      if (clientWs.readyState === clientWs.OPEN) {
        clientWs.send(JSON.stringify({ error: `Failed to initiate Live session: ${connErr.message}` }));
        clientWs.close();
      }
      return;
    }

    clientWs.on('message', (data: any) => {
      try {
        const payload = JSON.parse(data.toString());
        if (payload.audio && session) {
          session.sendRealtimeInput({
            audio: {
              data: payload.audio,
              mimeType: 'audio/pcm;rate=16000',
            },
          });
        }
      } catch (err: any) {
        console.warn('[Live Client Message Parse Error]', err.message);
      }
    });

    clientWs.on('close', () => {
      console.log('[Live WebSocket] Client disconnected');
      if (session) {
        try {
          session.close();
        } catch {}
      }
    });
  });
}
