// Shared edge-cascade search client for Pages Functions.
// Tavily -> Exa -> Brave live behind /mcp (tool: web_search_racing); this
// module is the only place the chat/search Functions learn that a vendor
// exists. Never throws — callers degrade to an honest "search unavailable".

export interface SearchHit {
  title: string;
  url: string;
  snippet?: string;
}

export interface SearchBundle {
  provider: string;
  results: SearchHit[];
}

export interface EdgeSearchEnv {
  MCP_API_KEY?: string;
  STRIKE_TIPS_API_KEY?: string;
  BACKEND_API_KEY?: string;
}

export const EDGE_MCP_URL = 'https://striketips-mcp.gmphorg379.workers.dev/mcp';
export const SEARCH_TIMEOUT_MS = 8_000;
export const MAX_SEARCH_QUERY = 200;
export const MAX_SEARCH_RESULTS = 5;

// Server-side only: the browser never sees this key.
export function edgeSearchKey(env: EdgeSearchEnv): string | undefined {
  return env.MCP_API_KEY || env.STRIKE_TIPS_API_KEY || env.BACKEND_API_KEY;
}

// One JSON-RPC tools/call against the stateless MCP endpoint. SSE-framed
// responses are unwrapped; any failure returns null.
export async function fetchEdgeSearch(query: string, env: EdgeSearchEnv): Promise<SearchBundle | null> {
  const key = edgeSearchKey(env);
  const q = String(query || '').replace(/\s+/g, ' ').trim().slice(0, MAX_SEARCH_QUERY);
  if (!key || !q) return null;
  try {
    const resp = await fetch(EDGE_MCP_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'x-api-key': key,
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/call',
        params: { name: 'web_search_racing', arguments: { query: q } },
      }),
      signal: AbortSignal.timeout(SEARCH_TIMEOUT_MS),
    });
    if (!resp.ok) return null;
    const raw = await resp.text();
    const dataLine = raw.split('\n').find((line) => line.trim().startsWith('data:'));
    const payload = dataLine ? dataLine.trim().slice(5).trim() : raw;
    if (!payload) return null;
    const rpc: any = JSON.parse(payload);
    const text = rpc?.result?.content?.[0]?.text;
    if (typeof text !== 'string' || !text) return null;
    const parsed: any = JSON.parse(text);
    const results: SearchHit[] = (Array.isArray(parsed?.results) ? parsed.results : [])
      .filter((r: any) => r && r.title && r.url)
      .slice(0, MAX_SEARCH_RESULTS)
      .map((r: any) => ({ title: String(r.title), url: String(r.url), snippet: r.snippet ? String(r.snippet) : undefined }));
    return { provider: String(parsed?.provider || 'unknown'), results };
  } catch {
    return null;
  }
}

// Context block injected into the system instruction for every model class.
export function buildSearchContext(bundle: SearchBundle | null): string {
  const day = new Date().toISOString().slice(0, 10);
  if (!bundle || bundle.results.length === 0) {
    return `\n\n[LIVE WEB SEARCH — UNAVAILABLE (${day})]\nNo live web results could be retrieved (free-tier search budgets exhausted, provider error, or search key not configured). State plainly that live web search was unavailable and do not invent sources.`;
  }
  const lines = bundle.results
    .slice(0, MAX_SEARCH_RESULTS)
    .map((r, i) => `${i + 1}. ${r.title} — ${r.url}${r.snippet ? `\n   ${r.snippet}` : ''}`)
    .join('\n');
  return `\n\n[LIVE WEB SEARCH RESULTS — provider: ${bundle.provider}, fetched ${day}]\n${lines}\nUse these results when relevant, cite the source URLs, and say so if they do not cover the question. Never invent URLs.`;
}

export function toGroundingSources(bundle: SearchBundle | null): Array<{ title: string; url: string }> {
  return (bundle?.results || [])
    .slice(0, MAX_SEARCH_RESULTS)
    .map((r) => ({ title: r.title, url: r.url }));
}
