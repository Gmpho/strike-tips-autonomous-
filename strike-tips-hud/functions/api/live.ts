// Pages Function: /api/live — Gemini Live voice bridge (WebSocket).
// Production port of server/live-service.ts (dev-only vite plugin).
// Raw WebSocket relay (no Node `ws` dep, no SDK): browser <--JSON--> Worker
// <--Live API WS--> Gemini. Keeps the browser protocol identical so
// LiveVoiceModal works unmodified: {ready, audio, text, interrupted,
// closed, error} down, {audio: base64pcm} up.
//
// Spend protection: 5 upgrades/min per IP; sessions auto-close after 10 min.
// Model defaults to the cloud agent's pick, overridable via LIVE_MODEL env.

import { hitRate as boundedHitRate, type RateEntry } from '../lib/rate-limit.ts';

interface Env {
  GEMINI_API_KEY?: string;
  LIVE_MODEL?: string;
}

const LIVE_SYSTEM_INSTRUCTION = `You are Strike Tips Live Racing Agent, an interactive voice assistant for South African horse racing.
- Speak in natural, concise, clear conversational sentences suitable for speech audio.
- Guide users on upcoming races, runners, form, track conditions, odds value, and bankroll staking.
- Keep spoken answers brief, punchy, and professional (avoid reading long tables aloud).`;

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 5; // upgrades/min per IP
const MAX_SESSION_MS = 10 * 60_000;
// Bounded store (shared limiter): evict-on-rollover + hard key cap.
const rateStore = new Map<string, RateEntry>();
// Concurrency ceilings (isolate-local best-effort — documented limitation):
// one live session per IP, a handful isolate-wide. Keyless spend surface
// stays capped even if per-IP limits are bypassed via many IPs.
const GLOBAL_LIVE_CAP = 10;
const activeSessions = new Set<WebSocket>();
const liveIps = new Map<WebSocket, string>();

function hitRate(ip: string): boolean {
  return boundedHitRate(rateStore, ip, RATE_MAX, RATE_WINDOW_MS);
}

// Frame throttle (pure, unit-testable): audio frames arrive ~constantly from
// the mic relay; a runaway client cannot push more than FRAME_RATE_PER_SEC
// upstream (burst bucket). Returns an allow() closure — true = relay frame.
export function makeFrameThrottle(ratePerSec: number, burst: number): () => boolean {
  let tokens = burst;
  let last = Date.now();
  return (): boolean => {
    const now = Date.now();
    tokens = Math.min(burst, tokens + ((now - last) / 1000) * ratePerSec);
    last = now;
    if (tokens < 1) return false; // throttle: drop, upstream stays within relay budget
    tokens -= 1;
    return true;
  };
}

const FRAME_BURST = 200;
const FRAME_RATE_PER_SEC = 80;

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
  // Concurrency ceilings: an IP with a live session cannot open a second
  // one, and the isolate never relays more than GLOBAL_LIVE_CAP at once.
  if ([...liveIps.values()].filter((v) => v === ip).length >= 1) {
    return new Response('Live session already active for this IP', { status: 429 });
  }
  if (activeSessions.size >= GLOBAL_LIVE_CAP) {
    return new Response('Live capacity reached', { status: 429 });
  }

  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair) as [WebSocket, WebSocket];
  server.accept();

  const model = env.LIVE_MODEL || 'gemini-3.8-live';
  let upstream: WebSocket | null = null;
  let closed = false;
  const trackLive = () => {
    activeSessions.add(server);
    liveIps.set(server, ip);
  };
  const closeAll = () => {
    if (closed) return;
    closed = true;
    activeSessions.delete(server);
    liveIps.delete(server);
    try { upstream?.close(); } catch { /* noop */ }
    try { server.close(); } catch { /* noop */ }
  };
  trackLive();
  const allowFrame = makeFrameThrottle(FRAME_RATE_PER_SEC, FRAME_BURST);
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
        if (!allowFrame()) return; // throttled: frame dropped
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
