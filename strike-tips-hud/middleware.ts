export const config = {
  matcher: '/api/:path*',
}

export default async function middleware(request: Request) {
  const url = new URL(request.url)
  const targetUrl = `https://gmpho--strike-tips-racing-serve-api.modal.run${url.pathname}${url.search}`

  const headers = new Headers(request.headers)
  headers.set('X-API-KEY', process.env.STRIKE_TIPS_API_KEY || '')

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.body,
  })

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  })
}
