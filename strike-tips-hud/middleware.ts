const CLOUDFLARE_ENDPOINTS = new Set([
  '/api/health', '/api/edge', '/api/kelly', '/api/circuit',
  '/api/bayesian', '/api/keywords', '/api/evaluate', '/api/verify-card',
  '/api/patch-html', '/api/racing/form', '/api/racing/odds',
  '/api/knowledge',
])

// Backend origins in priority order. Primary (Modal) fails → next origin serves,
// so a Modal credit outage degrades to Cloud Run instead of going dark.
// Set BACKEND_FALLBACK_ORIGIN in Vercel env vars to your Cloud Run URL.
const FALLBACK_ORIGIN = (process.env.BACKEND_FALLBACK_ORIGIN || '').replace(/\/$/, '')
const BACKEND_ORIGINS: string[] = [
  'https://gmpho--strike-tips-racing-serve-api.modal.run',
  ...(FALLBACK_ORIGIN ? [FALLBACK_ORIGIN] : []),
]

// Remember the last healthy origin for 60s to avoid probing on every request.
let healthyOrigin: string | null = null
let healthyAt = 0
const HEALTH_TTL_MS = 60_000

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

export default async function middleware(request: Request) {
  const url = new URL(request.url)
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

  // Fast path: cached healthy origin within TTL
  if (healthyOrigin && Date.now() - healthyAt < HEALTH_TTL_MS) {
    headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')
    const response = await fetchWithTimeout(
      `${healthyOrigin}${url.pathname}${url.search}`,
      { method: request.method, headers, body: request.body },
      25_000,
    )
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
  }

  // Probe origins in priority order — first success wins and is cached.
  for (const origin of BACKEND_ORIGINS) {
    try {
      headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')
      const response = await fetchWithTimeout(
        `${origin}${url.pathname}${url.search}`,
        { method: request.method, headers, body: request.body },
        25_000,
      )
      // Origin answered — treat as healthy even for 4xx (auth handled downstream).
      if (response.status < 500 || response.status === 401 || response.status === 404) {
        healthyOrigin = origin
        healthyAt = Date.now()
        return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
      }
      // 5xx → try next origin
    } catch {
      // Network error / timeout → try next origin
    }
  }

  // All origins failed — surface a clean 503 instead of hanging.
  return new Response(JSON.stringify({ detail: 'All backend origins unavailable' }), {
    status: 503,
    headers: { 'content-type': 'application/json' },
  })
}
