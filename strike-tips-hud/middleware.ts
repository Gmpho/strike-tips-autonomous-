const CLOUDFLARE_ENDPOINTS = new Set([
  '/api/health', '/api/edge', '/api/kelly', '/api/circuit',
  '/api/bayesian', '/api/keywords', '/api/evaluate', '/api/verify-card',
  '/api/patch-html', '/api/racing/form', '/api/racing/odds',
  '/api/knowledge',
])

export const config = {
  matcher: ['/api/:path*', '/v1/:path*', '/mcp'],
}

export default async function middleware(request: Request) {
  const url = new URL(request.url)
  const isCloudflare = Array.from(CLOUDFLARE_ENDPOINTS).some(ep => url.pathname.startsWith(ep)) ||
                       url.pathname.startsWith('/api/racing/evaluate/') ||
                       url.pathname === '/mcp'

  if (isCloudflare) {
    const targetUrl = `https://striketips-mcp.gmphorg379.workers.dev${url.pathname}${url.search}`
    const headers = new Headers(request.headers)
    headers.set('x-api-key', process.env.STRIKE_TIPS_API_KEY || '')
    const response = await fetch(targetUrl, { method: request.method, headers, body: request.body })
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
  }

  const targetUrl = `https://gmpho--strike-tips-racing-serve-api.modal.run${url.pathname}${url.search}`
  const headers = new Headers(request.headers)
  headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')
  const response = await fetch(targetUrl, { method: request.method, headers, body: request.body })
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers })
}
