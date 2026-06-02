const API_KEY = import.meta.env.VITE_STRIKE_TIPS_API_KEY || ''

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  if (API_KEY) {
    headers.set('X-API-KEY', API_KEY)
  }
  return fetch(input, { ...init, headers })
}
