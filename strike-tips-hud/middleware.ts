// Cloudflare Worker MCP endpoints — these are served by the Cloudflare
// Worker (always-on, free) and are separate from the primary backend.
const CLOUDFLARE_ENDPOINTS = new Set([
  '/api/health', '/api/edge', '/api/kelly', '/api/circuit',
  '/api/bayesian', '/api/keywords', '/api/evaluate', '/api/verify-card',
  '/api/patch-html', '/api/racing/form', '/api/racing/odds',
  '/api/knowledge',
])

// PRIMARY backend — Modal is always preferred.
const MODAL_ORIGIN = 'https://gmpho--strike-tips-racing-serve-api.modal.run'
// Optional fallback origin (Cloud Run / self-hosted). Leave unset to run on
// Modal only. Set BACKEND_FALLBACK_ORIGIN in Vercel env vars to enable it.
// No fallback URL is hard-coded here — Modal is always primary.
const FALLBACK_ORIGIN = (process.env.BACKEND_FALLBACK_ORIGIN || '').replace(/\/$/, '')
const BACKEND_ORIGINS: string[] = [
  MODAL_ORIGIN,
  ...(FALLBACK_ORIGIN ? [FALLBACK_ORIGIN] : []),
]

// A dark backend (e.g. suspended Modal function) answers 404 quickly — that is
// NOT health. Origins are validated with a real /api/system/health probe, and
// the first *healthy* one wins, so Modal stays primary automatically.
let healthyOrigin: string | null = null
let healthyAt = 0
const HEALTH_TTL_MS = 60_000
const PROBE_TIMEOUT_MS = 3_000
const FORWARD_TIMEOUT_MS = 25_000

// ── Security: rate limiting (fixed window, in-memory) ───────────────
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 100; // 100 req/min per IP
const rateStore = new Map<string, { count: number; resetAt: number }>();

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = rateStore.get(ip);
  if (!entry || now > entry.resetAt) {
    rateStore.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return false;
  }
  entry.count++;
  if (entry.count > RATE_LIMIT_MAX) return true;
  return false;
}

// ── Security: auth check for sensitive endpoints ────────────────────
const SENSITIVE_PATHS = [
  '/api/agent/kill',
  '/api/agent/reset',
];
function isSensitive(pathname: string): boolean {
  return SENSITIVE_PATHS.some(p => pathname.startsWith(p));
}
function isAuthorizedRequest(req: Request): boolean {
  const key = req.headers.get('x-api-key') || req.headers.get('X-API-KEY') || req.headers.get('authorization')?.replace(/^Bearer\s+/i, '') || '';
  const expected = process.env.STRIKE_TIPS_API_KEY || '';
  // If no expected key configured, deny by default (fail-closed) for sensitive paths
  if (!expected) return false;
  return key === expected;
}

export const config = {
  matcher: ['/api/:path*', '/v1/:path*', '/mcp'],
}

async function fetchWithTimeout(targetUrl: string, init: RequestInit, ms: number): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  try {
    return await fetch(targetUrl, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

async function probeHealthy(origin: string): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${origin}/api/system/health`, { method: 'GET' }, PROBE_TIMEOUT_MS)
    return res.ok
  } catch {
    return false
  }
}

export default async function middleware(request: Request) {
  const url = new URL(request.url)

  // ── Rate limiting ─────────────────────────────────────────────
  const ip = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || request.headers.get('x-real-ip') || 'unknown';
  if (isRateLimited(ip)) {
    return new Response(JSON.stringify({ error: 'Too Many Requests' }), {
      status: 429,
      headers: { 'Content-Type': 'application/json', 'Retry-After': '60' },
    });
  }

  // ── Auth for sensitive endpoints (fail-closed) ────────────────
  if (isSensitive(url.pathname) && !isAuthorizedRequest(request)) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const isCloudflare = Array.from(CLOUDFLARE_ENDPOINTS).some(ep => url.pathname.startsWith(ep)) ||
                       url.pathname.startsWith('/api/racing/evaluate/') ||
                       url.pathname === '/mcp'

  const headers = new Headers(request.headers)

  if (isCloudflare) {
    const targetUrl = `https://striketips-mcp.gmphorg379.workers.dev${url.pathname}${url.search}`
    headers.set('x-api-key', process.env.STRIKE_TIPS_API_KEY || '')
    const response = await fetch(targetUrl, { method: request.method, headers, body: request.body })
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
  }

  // Fast path: cached healthy origin within TTL (Modal by default).
  if (healthyOrigin && Date.now() - healthyAt < HEALTH_TTL_MS) {
    headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')
    const response = await fetchWithTimeout(
      `${healthyOrigin}${url.pathname}${url.search}`,
      { method: request.method, headers, body: request.body },
      FORWARD_TIMEOUT_MS,
    )
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
  }

  // Probe origins in priority order — first healthy one wins (Modal first).
  for (const origin of BACKEND_ORIGINS) {
    if (await probeHealthy(origin)) {
      healthyOrigin = origin
      healthyAt = Date.now()
      headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')
      const response = await fetchWithTimeout(
        `${origin}${url.pathname}${url.search}`,
        { method: request.method, headers, body: request.body },
        FORWARD_TIMEOUT_MS,
      )
      return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
    }
  }

  // No origin healthy — forward to the primary (Modal) as a last resort.
  headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')
  const response = await fetchWithTimeout(
    `${BACKEND_ORIGINS[0]}${url.pathname}${url.search}`,
    { method: request.method, headers, body: request.body },
    FORWARD_TIMEOUT_MS,
  )
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
}
