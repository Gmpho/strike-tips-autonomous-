// Bounded in-memory sliding-window limiter shared by all edge Functions.
// Isolate-local by design (documented limitation: not a distributed limiter);
// the hard cap + eviction guarantee is that no store grows without bound
// under spoofed-IP load (harden-pages-functions: "limiter state is bounded").

export interface RateEntry {
  count: number;
  resetAt: number;
}

export const RATE_STORE_CAP = 10_000;

function evict(store: Map<string, RateEntry>, now: number): void {
  // Cheap pass first: drop everything already expired.
  for (const [k, v] of store) {
    if (now > v.resetAt) store.delete(k);
  }
  if (store.size < RATE_STORE_CAP) return;
  // Still full (all live): evict the soonest-expiring 10%.
  const keys = [...store.entries()].sort((a, b) => a[1].resetAt - b[1].resetAt);
  const drop = Math.ceil(RATE_STORE_CAP * 0.1);
  for (let i = 0; i < drop && i < keys.length; i++) store.delete(keys[i][0]);
}

export function hitRate(
  store: Map<string, RateEntry>,
  key: string,
  max: number,
  windowMs: number,
): boolean {
  const now = Date.now();
  const entry = store.get(key);
  if (!entry || now > entry.resetAt) {
    if (store.size >= RATE_STORE_CAP) evict(store, now);
    store.set(key, { count: 1, resetAt: now + windowMs });
    return false;
  }
  entry.count++;
  return entry.count > max;
}