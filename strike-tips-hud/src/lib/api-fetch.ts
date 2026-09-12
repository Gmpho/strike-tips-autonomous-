import { directBackendUrl } from './backend-origin'

const inFlight = new Map<string, Promise<Response>>()
const MAX_RETRIES = 2
const RETRY_DELAYS = [1000, 2000]

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // Keyless reads go direct to the backend origin (bypasses the Function
  // proxy: no invocations, no origin transfer). Keyed endpoints stay
  // same-origin so the proxy can inject the API secret server-side.
  const direct = typeof input === 'string' ? directBackendUrl(input) : null
  const target: RequestInfo | URL = direct ?? input
  const url = typeof target === 'string' ? target : target instanceof URL ? target.href : target.url
  const key = `${url}|${JSON.stringify(init?.body ?? '')}`

  const existing = inFlight.get(key)
  if (existing) return existing.then(r => r.clone())

  const headers = new Headers(init?.headers)

  const execute = async (attempt: number): Promise<Response> => {
    const res = await fetch(target, { ...init, headers })
    if (res.status === 429 && attempt < MAX_RETRIES) {
      await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt]))
      return execute(attempt + 1)
    }
    return res
  }

  const promise = execute(0)
  inFlight.set(key, promise)
  promise.finally(() => inFlight.delete(key))

  return promise
}
