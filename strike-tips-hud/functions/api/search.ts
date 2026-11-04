// Pages Function: GET/POST /api/search?q=... — keyless same-origin proxy to
// the edge free-tier cascade (Tavily -> Exa -> Brave). Used by browser-local
// WebLLM grounding and UI source chips; the edge key stays server-side.
// Spend guard: per-IP rate limit + capped query; cascade KV meters hold the
// monthly ceilings.

import { hitRate, type RateEntry } from '../lib/rate-limit.ts';
import { fetchEdgeSearch, MAX_SEARCH_QUERY, type EdgeSearchEnv } from '../lib/edge-search.ts';

type Env = EdgeSearchEnv;

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 30; // cascade calls/min per IP
const store = new Map<string, RateEntry>();

function corsHeaders(origin: string): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(url.origin) });
  }
  if (request.method !== 'GET' && request.method !== 'POST') {
    return Response.json({ error: 'Method Not Allowed' }, { status: 405, headers: corsHeaders(url.origin) });
  }
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (hitRate(store, ip, RATE_MAX, RATE_WINDOW_MS)) {
    return Response.json(
      { error: 'Too Many Requests' },
      { status: 429, headers: { ...corsHeaders(url.origin), 'Retry-After': '60' } },
    );
  }

  let query = url.searchParams.get('q') || '';
  if (!query && request.method === 'POST') {
    try {
      const body: any = await request.json();
      query = String(body?.query || '');
    } catch {
      /* malformed body -> empty query handled below */
    }
  }
  const q = query.replace(/\s+/g, ' ').trim().slice(0, MAX_SEARCH_QUERY);
  if (!q) {
    return Response.json({ error: 'Missing q' }, { status: 400, headers: corsHeaders(url.origin) });
  }

  const bundle = await fetchEdgeSearch(q, env);
  if (!bundle) {
    return Response.json(
      { query: q, provider: 'none', count: 0, results: [], available: false },
      { headers: corsHeaders(url.origin) },
    );
  }
  return Response.json(
    {
      query: q,
      provider: bundle.provider,
      count: bundle.results.length,
      results: bundle.results,
      available: bundle.results.length > 0,
    },
    { headers: corsHeaders(url.origin) },
  );
};
