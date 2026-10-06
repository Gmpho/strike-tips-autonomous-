// Cloudflare Pages Function: /v1/* reverse proxy (OpenAI-compatible chat
// endpoints used by the HUD). Always Modal + server-side secret injection.

interface Env {
  BACKEND_API_KEY?: string;
  SESSION_SECRET?: string;
}

import { verify, SESSION_COOKIE_NAME, scopeAllows } from "../lib/session";

const MODAL_ORIGIN = 'https://gmpho--strike-tips-racing-serve-api.modal.run';

// LLM inference is attacker-funded compute: tight per-IP budget on top of
// the backend key check (Sep-2026 audit: open inference = Denial of Wallet).
const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 30;
const rateStore = new Map<string, { count: number; resetAt: number }>();

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);

  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': url.origin,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-API-KEY, x-api-key, Authorization',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  const ip = request.headers.get('cf-connecting-ip')
    || request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
    || 'unknown';

  // Inbound auth (Oct-2026 hardening): the old code only rate-limited.
  // Inference is attacker-funded compute — require the master key OR a
  // proof-of-browser Turnstile session. Health/models stay open (monitoring).
  const openPaths = ['/v1/health', '/v1/models'];
  if (!openPaths.includes(url.pathname)) {
    const caller = request.headers.get('x-api-key') || request.headers.get('X-API-KEY')
      || request.headers.get('authorization')?.replace(/^Bearer\s+/i, '') || '';
    let allowed = Boolean(env.BACKEND_API_KEY) && caller === env.BACKEND_API_KEY;
    if (!allowed && env.SESSION_SECRET) {
      const cookie = request.headers.get('Cookie') || '';
      const raw = cookie.split(';').map((c) => c.trim())
        .find((c) => c.startsWith(`${SESSION_COOKIE_NAME}=`));
      const token = raw ? decodeURIComponent(raw.slice(SESSION_COOKIE_NAME.length + 1)) : '';
      if (token && scopeAllows('/v1/chat')) {
        const claims = await verify({ secret: env.SESSION_SECRET, token });
        if (claims) allowed = true;
      }
    }
    if (!allowed) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }
  }

  const now = Date.now();
  const entry = rateStore.get(ip);
  if (!entry || now > entry.resetAt) {
    rateStore.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
  } else {
    entry.count++;
    if (entry.count > RATE_MAX) {
      return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { 'Retry-After': '60' } });
    }
  }

  const headers = new Headers(request.headers);
  headers.set('X-API-KEY', env.BACKEND_API_KEY || '');

  const upstream = await fetch(`${MODAL_ORIGIN}${url.pathname}${url.search}`, {
    method: request.method,
    headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
  } as RequestInit);
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  });
};
