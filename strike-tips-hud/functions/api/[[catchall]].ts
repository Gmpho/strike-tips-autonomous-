// Cloudflare Pages Function: /api/* reverse proxy.
// Routing: MCP/compute-light paths -> striketips-mcp worker (always-free edge)
// everything else            -> Modal backend (primary)
// The API secret is injected server-side from env; browsers never see it.
//
// Only keyed endpoints should reach here — keyless reads go direct to the
// origins (see src/lib/backend-origin.ts), keeping invocations minimal.

interface Env {
  BACKEND_API_KEY?: string;
  BACKEND_FALLBACK_ORIGIN?: string;
  SESSION_SECRET?: string;
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
const RATE_MAX = 100; // reads/min per IP
const WRITE_RATE_MAX = 20; // writes/min per IP (bet placement, config, healing)
const rateStore = new Map<string, { count: number; resetAt: number }>();
const writeStore = new Map<string, { count: number; resetAt: number }>();

function hitRate(
  store: Map<string, { count: number; resetAt: number }>,
  ip: string,
  max: number,
): boolean {
  const now = Date.now();
  const entry = store.get(ip);
  if (!entry || now > entry.resetAt) {
    store.set(ip, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return false;
  }
  entry.count++;
  return entry.count > max;
}

// State-changing API families: the proxy never spends the master key here
// on an anonymous caller's behalf (Sep-2026 audit: confused-deputy). A valid
// browser session token (see functions/_middleware.ts + lib/session.ts) is
// proof-of-browser for the SESSION families only — never for betting writes,
// tasks, or the master-key-only actions below.
const WRITE_PREFIXES = [
  '/api/betting/',
  '/api/config',
  '/api/healing/',
  '/api/tasks/',
  '/api/agent/kill',
  '/api/agent/reset',
];

// Subset of WRITE_PREFIXES that a session token may satisfy. /api/betting/*,
// /api/tasks/* and /api/agent/kill|reset stay master-key-only.
const SESSION_WRITE_PREFIXES = [
  '/api/config',
  '/api/healing/',
  '/api/dreaming/',
];

function readSessionCookie(request: Request): string {
  const raw = request.headers.get('Cookie') || '';
  const parts = raw.split(';');
  for (const part of parts) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq).trim() === 'st_session') return decodeURIComponent(part.slice(eq + 1).trim());
  }
  return '';
}

async function hasValidSession(request: Request, env: Env): Promise<boolean> {
  const secret = env.SESSION_SECRET || '';
  const token = readSessionCookie(request);
  if (!secret || !token) return false;
  try {
    const { verify } = await import('../lib/session.ts');
    const claims = await verify({ secret, token });
    return claims !== null;
  } catch {
    return false;
  }
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
  if (hitRate(rateStore, ip, RATE_MAX)) {
    return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { 'Retry-After': '60' } });
  }

  const isWrite = !['GET', 'HEAD', 'OPTIONS'].includes(request.method)
    && WRITE_PREFIXES.some((p) => matches(url.pathname, p));

  // Sensitive actions + all state-changing calls: caller must present the
  // key (fail-closed). Reads keep flowing with server-side injection.
  // Proof-of-browser branch (master key first and independently below):
  // a valid session token satisfies SESSION_WRITE_PREFIXES only.
  const sensitive = SENSITIVE_PREFIXES.some((p) => matches(url.pathname, p));
  const sessionScoped = !sensitive
    && !['GET', 'HEAD', 'OPTIONS'].includes(request.method)
    && SESSION_WRITE_PREFIXES.some((p) => matches(url.pathname, p));
  const needsCallerKey = isWrite || sensitive;
  if (needsCallerKey) {
    const caller = request.headers.get('x-api-key') || request.headers.get('X-API-KEY')
      || request.headers.get('authorization')?.replace(/^Bearer\s+/i, '') || '';
    const masterOk = Boolean(env.BACKEND_API_KEY) && caller !== '' && caller === env.BACKEND_API_KEY;
    // Master key wins outright; for the session-scoped families a valid
    // browser session token is also sufficient. Nothing else is.
    if (!masterOk) {
      if (!(sessionScoped && await hasValidSession(request, env))) {
        return Response.json({ error: 'Unauthorized' }, { status: 401 });
      }
    }
  }
  if (isWrite && hitRate(writeStore, ip, WRITE_RATE_MAX)) {
    return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { 'Retry-After': '60' } });
  }

  const isCF = CF_PREFIXES.some((p) => matches(url.pathname, p))
    || url.pathname.startsWith('/api/racing/evaluate/');
  const origin = isCF ? CF_MCP_ORIGIN : MODAL_ORIGIN;

  const headers = new Headers(request.headers);
  headers.set('X-API-KEY', env.BACKEND_API_KEY || ''); // env typed as Env, always a string here

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
    // Last resort: Modal directly (the primary origin for non-worker paths).
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
