// Traffic-triggered Betway refresh (26 Nov 2026).
//
// The scheduled cron runs on Cloudflare's "underutilized machines" — a
// different colo from the one that serves HUD requests. Both Betway and
// SportyBet WAFs refuse that colo's egress (HTTP 403), so the cron has never
// written a single `betway:raw:*` key. The same GetDaily call from a JNB
// request colo answers 200 with 204 events.
//
// The HUD polls /api/racing/odds every 15 seconds from South Africa, so its
// request already lands in the colo Betway accepts. Piggyback the existing
// cronFetchBetway on that traffic, rate-limited and in the background via
// ctx.waitUntil: it writes the same KV keys, so Modal's reader is unchanged.
//
// Rate limit is per isolate (no extra KV write): 8 min ≈ 180 runs/day ≈ 540
// KV writes, leaving room under the free tier's 1,000/day once the hourly
// cron fallback (~72 writes) is included.

import type { CronEnv, CronResult } from "./betway-cron";

export const TRAFFIC_FETCH_MIN_GAP_MS = 8 * 60_000;

/** True when enough time has elapsed (or the clock moved backwards). */
export function shouldTriggerFetch(
  now: number,
  last: number,
  minGapMs: number = TRAFFIC_FETCH_MIN_GAP_MS,
): boolean {
  if (!Number.isFinite(now) || last <= 0 || now < last) return true;
  return now - last >= minGapMs;
}

export interface TrafficFetcherOptions {
  fetchBetway: (env: CronEnv) => Promise<CronResult>;
  now?: () => number;
  log?: (line: string) => void;
  minGapMs?: number;
}

export type TrafficFetcher = (
  env: CronEnv,
  ctx: ExecutionContext,
  colo?: string,
) => boolean;

/**
 * Build a per-isolate trigger. The timestamp is reserved *before* the async
 * fetch so parallel HUD polls cannot start a second batch while the first is
 * still in flight.
 */
export function createTrafficFetcher(options: TrafficFetcherOptions): TrafficFetcher {
  let last = 0;
  const now = options.now || Date.now;
  const minGap = options.minGapMs ?? TRAFFIC_FETCH_MIN_GAP_MS;

  return (env, ctx, colo) => {
    const stamp = now();
    if (!shouldTriggerFetch(stamp, last, minGap)) return false;
    last = stamp;

    ctx.waitUntil(
      Promise.resolve()
        .then(() => options.fetchBetway(env))
        .then((result) => {
          options.log?.(
            `betway-traffic-fetch colo=${colo || "?"} ms=${Math.max(0, now() - stamp)} ${JSON.stringify(result)}`,
          );
        })
        .catch((error: unknown) => {
          options.log?.(
            `betway-traffic-fetch failed colo=${colo || "?"} ${String(error)}`,
          );
        }),
    );
    return true;
  };
}
