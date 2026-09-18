// Pages Function: /api/live — Gemini Live voice bridge (WebSocket).
// Production port of server/live-service.ts (dev-only vite plugin).
// Raw WebSocket relay (no Node `ws` dep, no SDK): browser <--JSON--> Worker
// <--Live API WS--> Gemini. Keeps the browser protocol identical so
// LiveVoiceModal works unmodified: {ready, audio, text, interrupted,
// closed, error} down, {audio: base64pcm} up.
//
// Spend protection: 5 upgrades/min per IP; sessions auto-close after 10 min.
// Model defaults to the cloud agent's pick, overridable via LIVE_MODEL env.

interface Env {
  GEMINI_API_KEY?: string;
  LIVE_MODEL?: string;
}

const LIVE_SYSTEM_INSTRUCTION = `You are Strike Tips Live Racing Agent, an interactive voice assistant for South African horse racing.
- Speak in natural, concise, clear conversational sentences suitable for speech audio.
- Guide users on upcoming races, runners, form, track conditions, odds value, and bankroll staking.
- Keep spoken answers brief, punchy, and professional (avoid reading long tables aloud).`;

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 5;
const MAX_SESSION_MS = 10 * 60_000;
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

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  if (request.headers.get('Upgrade') !== 'websocket') {
    return new Response('WebSocket upgrade required', { status: 426 });
  }
  if (!env.GEMINI_API_KEY) {
    return new Response('GEMINI_API_KEY is not configured on the server.', { status: 400 });
  }
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (hitRate(ip)) {
    return new Response('Too Many Requests', { status: 429 });
  }

  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair) as [WebSocket, WebSocket];
  server.accept();

  const model = env.LIVE_MODEL || 'gemini-3.8-live';
  let upstream: WebSocket | null = null;
  let closed = false;
  const closeAll = () => {
    if (closed) return;
    closed = true;
    try { upstream?.close(); } catch { /* noop */ }
    try { server.close(); } catch { /* noop */ }
  };
  setTimeout(closeAll, MAX_SESSION_MS);

  const send = (obj: unknown) => {
    try { server.send(JSON.stringify(obj)); } catch { /* noop */ }
  };

  try {
    upstream = new WebSocket(
      `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key=${env.GEMINI_API_KEY}`,
    );
  } catch (e: any) {
    send({ error: `Failed to initiate Live session: ${e.message}` });
    closeAll();
    return new Response(null, { status: 101, webSocket: client } as any);
  }

  upstream.addEventListener('open', () => {
    try {
      upstream!.send(JSON.stringify({
        setup: {
          model: `models/${model}`,
          generationConfig: {
            responseModalities: ['AUDIO'],
            speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Zephyr' } } },
          },
          systemInstruction: { parts: [{ text: LIVE_SYSTEM_INSTRUCTION }] },
        },
      }));
    } catch (e: any) {
      send({ error: `Live setup failed: ${e.message}` });
      closeAll();
    }
  });

  upstream.addEventListener('message', (evt: any) => {
    try {
      const msg = JSON.parse(typeof evt.data === 'string' ? evt.data : '');
      if (msg.setupComplete) {
        send({ ready: true, model });
        return;
      }
      const parts = msg.serverContent?.modelTurn?.parts || [];
      for (const part of parts) {
        if (part.inlineData?.data) send({ audio: part.inlineData.data });
        if (part.text) send({ text: part.text });
      }
      if (msg.serverContent?.interrupted) send({ interrupted: true });
    } catch { /* partial frame */ }
  });

  const upstreamDown = (reason: string) => {
    send({ error: reason });
    closeAll();
  };
  upstream.addEventListener('close', () => { send({ closed: true }); closeAll(); });
  upstream.addEventListener('error', () => upstreamDown('Live session error'));

  server.addEventListener('message', (evt: any) => {
    try {
      const payload = JSON.parse(typeof evt.data === 'string' ? evt.data : '');
      if (payload.audio && upstream && (upstream as any).readyState === 1) {
        upstream.send(JSON.stringify({
          realtimeInput: { audio: { data: payload.audio, mimeType: 'audio/pcm;rate=16000' } },
        }));
      }
    } catch { /* ignore malformed client frames */ }
  });
  server.addEventListener('close', closeAll);
  server.addEventListener('error', closeAll);

  return new Response(null, { status: 101, webSocket: client } as any);
};
