// Cloudflare Pages Function: /v1/* reverse proxy (OpenAI-compatible chat
// endpoints used by the HUD). Always Modal + server-side secret injection.

interface Env {
  BACKEND_API_KEY?: string;
}

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
