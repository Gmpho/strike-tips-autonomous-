import { directBackendUrl } from './backend-origin'

const inFlight = new Map<string, Promise<Response>>()
const MAX_RETRIES = 2
const RETRY_DELAYS = [1000, 2000]
// Direct Modal reads bypass the Pages proxy (no 25s abort there), and a
// cold backend hangs for minutes — cap every call so the UI fails fast
// instead of pending for 2.5 min (Sep-2026 outage pattern).
const DIRECT_TIMEOUT_MS = 25_000

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // Keyless reads go direct to the backend origin (bypasses the Function
  // proxy: no invocations, no origin transfer). Keyed endpoints stay
  // same-origin so the proxy can inject the API secret server-side.
  // `credentials: 'same-origin'` is explicit on purpose: some contexts
  // (e.g. Telegram webview) default to `omit`, and without the HttpOnly
  // session cookie the write path 401s forever.
  const direct = typeof input === 'string' ? directBackendUrl(input) : null
  const target: RequestInfo | URL = direct ?? input
  const url = typeof target === 'string' ? target : target instanceof URL ? target.href : target.url
  const key = `${url}|${JSON.stringify(init?.body ?? '')}`

  const existing = inFlight.get(key)
  if (existing) return existing.then(r => r.clone())

  const headers = new Headers(init?.headers)

  const execute = async (attempt: number): Promise<Response> => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), DIRECT_TIMEOUT_MS)
    const signals = [controller.signal, init?.signal].filter((s): s is AbortSignal => !!s)
    const signal = signals.length > 1 && typeof AbortSignal.any === 'function'
      ? AbortSignal.any(signals)
      : signals[0]
    // Only retry replayable bodies (streams/FormData can't resend).
    const canRetry = !init?.body || typeof init.body === 'string'
    try {
      const res = await fetch(target, { ...init, headers, signal, credentials: 'same-origin' })
      if ((res.status === 429 || res.status === 503) && canRetry && attempt < MAX_RETRIES) {
        await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]))
        return execute(attempt + 1)
      }
      return res
    } finally {
      clearTimeout(timer)
    }
  }

  const promise = execute(0)
  inFlight.set(key, promise)
  promise.finally(() => inFlight.delete(key))

  return promise
}
