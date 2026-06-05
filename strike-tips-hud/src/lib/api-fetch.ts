const inFlight = new Map<string, Promise<Response>>()
const MAX_RETRIES = 2
const RETRY_DELAYS = [1000, 2000]

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  const key = `${url}|${JSON.stringify(init?.body ?? '')}`

  const existing = inFlight.get(key)
  if (existing) return existing.then(r => r.clone())

  const headers = new Headers(init?.headers)

  const execute = async (attempt: number): Promise<Response> => {
    const res = await fetch(input, { ...init, headers })
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
