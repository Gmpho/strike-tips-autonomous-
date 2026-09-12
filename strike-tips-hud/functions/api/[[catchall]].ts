// Cloudflare Pages Function: /api/* reverse proxy.
// Ports strike-tips-hud/middleware.ts (Vercel) routing:
// - MCP/compute-light paths -> striketips-mcp worker (always-free edge)
// - everything else          -> Modal backend (primary)
// The API secret is injected server-side from env; browsers never see it.
//
// Only keyed endpoints should reach here — keyless reads go direct to the
// origins (see src/lib/backend-origin.ts), keeping invocations minimal.

interface Env {
  BACKEND_API_KEY?: string;
  BACKEND_FALLBACK_ORIGIN?: string;
}

const MODAL_ORIGIN = 'https://gmpho--strike-tips-racing-serve-api.modal.run';
const CF_MCP_ORIGIN = 'https://striketips-mcp.gmphorg379.workers.dev';

const CF_PREFIXES = [
  '/api/health', '/api/edge', '/api/kelly', '/api/circuit',
  '/api/bayesian', '/api/keywords', '/api/evaluate', '/api/verify-card',
  '/api/patch-html', '/api/racing/form', '/api/racing/odds',
  '/api/knowledge',
];

const SENSITIVE_PREFIXES = ['/api/agent/kill', '/api/agent/reset'];

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 100;
const rateStore = new Map<string, { count: number; resetAt: number }>();

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = rateStore.get(ip);
  if (!entry || now > entry.resetAt) {
    rateStore.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return false;
  }
  entry.count++;
  return entry.count > RATE_MAX;
}

function matches(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(prefix.endsWith('/') ? prefix : prefix + '/');
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);

  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': url.origin,
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-API-KEY, x-api-key, Authorization',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  const ip = request.headers.get('cf-connecting-ip')
    || request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
    || 'unknown';
  if (isRateLimited(ip)) {
    return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { 'Retry-After': '60' } });
  }

  // Sensitive actions: caller must present the key (fail-closed).
  if (SENSITIVE_PREFIXES.some((p) => matches(url.pathname, p))) {
    const caller = request.headers.get('x-api-key') || request.headers.get('X-API-KEY')
      || request.headers.get('authorization')?.replace(/^Bearer\s+/i, '') || '';
    if (!env.BACKEND_API_KEY || caller !== env.BACKEND_API_KEY) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }
  }

  const isCF = CF_PREFIXES.some((p) => matches(url.pathname, p))
    || url.pathname.startsWith('/api/racing/evaluate/');
  const origin = isCF ? CF_MCP_ORIGIN : MODAL_ORIGIN;

  const headers = new Headers(request.headers);
  headers.set('X-API-KEY', env.BACKEND_API_KEY || '');

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25_000);
  try {
    const upstream = await fetch(`${origin}${url.pathname}${url.search}`, {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      signal: controller.signal,
    } as RequestInit);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    });
  } catch (e) {
    // Last resort: Modal directly (matches Vercel middleware fallback).
    if (!isCF) throw e;
    const headers2 = new Headers(request.headers);
    headers2.set('X-API-KEY', env.BACKEND_API_KEY || '');
    const upstream = await fetch(`${MODAL_ORIGIN}${url.pathname}${url.search}`, {
      method: request.method,
      headers: headers2,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
    } as RequestInit);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    });
  } finally {
    clearTimeout(timer);
  }
};
