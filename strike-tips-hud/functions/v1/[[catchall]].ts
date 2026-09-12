// Cloudflare Pages Function: /v1/* reverse proxy (OpenAI-compatible chat
// endpoints used by the HUD). Always Modal + server-side secret injection.

interface Env {
  BACKEND_API_KEY?: string;
}

const MODAL_ORIGIN = 'https://gmpho--strike-tips-racing-serve-api.modal.run';

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
