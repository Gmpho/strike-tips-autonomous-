// Direct-origin routing: keyless reads bypass the Pages Function proxy and
// go straight to the backend (zero Function invocations, zero origin
// transfer on our meter). Keyed endpoints stay same-origin so the Function
// can inject the API secret server-side.
//
// Path sets mirror the backends:
// - CF set  == Cloudflare MCP worker paths (striketips-mcp worker)
// - Modal keyless == Modal SAFE_PATHS in core_agent/core/security.py
// Keep both lists in sync with those sources when endpoints change.

export const MODAL_ORIGIN = 'https://gmpho--strike-tips-racing-serve-api.modal.run'
export const CF_MCP_ORIGIN = 'https://striketips-mcp.gmphorg379.workers.dev'

const CF_PREFIXES = [
  '/api/health', '/api/edge', '/api/kelly', '/api/circuit',
  '/api/bayesian', '/api/keywords', '/api/evaluate', '/api/verify-card',
  '/api/patch-html', '/api/racing/form', '/api/racing/odds',
  '/api/knowledge', '/api/racing/evaluate/', '/mcp',
]

// Exact paths keyless on Modal (query strings ignored when matching).
const MODAL_KEYLESS_EXACT = new Set([
  '/api/system/health',
  '/api/agent/chat', '/api/agent/chat/stream',
  '/api/agent/health', '/api/agent/tools', '/api/agent/models',
  '/api/agent/history',
  '/api/monitoring/stream',
  '/api/racing/exotics',
  '/api/news', '/api/news/images',
  '/api/telemetry',
])

// Prefixes keyless on Modal (boundary-aware: exact or followed by '/').
const MODAL_KEYLESS_PREFIXES = ['/api/legal/']

function matchesPrefix(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(prefix.endsWith('/') ? prefix : prefix + '/')
}

function pathOf(input: RequestInfo | URL): string | null {
  try {
    if (typeof input === 'string') {
      if (!input.startsWith('/')) return null // absolute URL: leave alone
      return input.split('?')[0]
    }
    if (input instanceof URL) return null // absolute: leave alone
    const u = (input as Request).url
    const parsed = new URL(u)
    // Only rewrite same-origin relative requests; leave direct ones alone.
    if (parsed.origin !== globalThis.location?.origin) return null
    return parsed.pathname
  } catch {
    return null
  }
}

/**
 * Resolve a same-origin relative /api/* (or /mcp) request to a direct
 * backend URL when the endpoint is keyless. Returns null when the request
 * must stay same-origin (keyed endpoint -> Pages Function proxy injects
 * the secret), when running under Vite dev (proxy handles it), or when the
 * input is already absolute.
 */
export function directBackendUrl(input: RequestInfo | URL): string | null {
  try {
    if ((import.meta as any).env?.DEV) return null
  } catch { /* non-Vite runtime: continue */ }
  const path = pathOf(input)
  if (!path) return null
  const raw = typeof input === 'string' ? input : (input as Request).url
  const suffix = typeof raw === 'string' && raw.startsWith('/')
    ? raw.slice(path.length) // keep ?query
    : ''
  if (CF_PREFIXES.some(p => matchesPrefix(path, p))) return `${CF_MCP_ORIGIN}${path}${suffix}`
  if (MODAL_KEYLESS_EXACT.has(path)) return `${MODAL_ORIGIN}${path}${suffix}`
  if (MODAL_KEYLESS_PREFIXES.some(p => path.startsWith(p))) return `${MODAL_ORIGIN}${path}${suffix}`
  return null
}
