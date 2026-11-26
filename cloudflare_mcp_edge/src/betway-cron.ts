// Betway fetch cron — Cloudflare-side egress.
//
// Modal's Azure egress is blocked by Betway's WAF on both the API and the
// racecard HTML (403 "Attention Required! | Cloudflare", verified 2026-11-22),
// and Modal cannot rely on reaching *.workers.dev either — that is blocked
// per Cloudflare colo (BOM/SIN 403, AMS 200), not globally. Cloudflare's own
// egress is accepted *in some colos* (JNB answers 200) but the cron scheduler
// runs on underutilized machines whose colo is refused (26 Nov 2026: every
// scheduled run died at `GetDaily HTTP 403` before writing any KV key). The
// frequent refresh is therefore triggered from HUD traffic in the good colo
// (src/betway-traffic.ts); this function stays the shared fetch implementation
// and the hourly cron is a cheap fallback.
//
// Division of labour:
//   Worker  → fetch Betway raw JSON, park it in KV (no parsing, no opinion)
//   Modal   → read KV over the Cloudflare REST API, parse, publish snapshot
//   HUD     → reads /api/racing/odds as before
//
// KV budget (free tier 1,000 writes/day): a run writes 2 slots + 1 cursor,
// and the daily index every third run → 3 × 288 + 96 = 960 writes.

export interface CronEnv {
  ODDS_KV: KVNamespace;
}

const TRACK_API = "https://www.betway.co.za/sportsapi/v1/TrackRacing";

// The browser fingerprint Betway accepts. A bare request without these gets
// "error code: 520" from Cloudflare even on a perfectly clean IP — verified
// 2026-11-22 (home IP: 520 without headers, 200 with them).
const BETWAY_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  Referer: "https://www.betway.co.za/sport/horse-racing",
  Origin: "https://www.betway.co.za",
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "en-ZA,en;q=0.9",
  "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
  "Sec-Ch-Ua-Mobile": "?0",
  "Sec-Ch-Ua-Platform": '"Windows"',
  "Sec-Fetch-Dest": "empty",
  "Sec-Fetch-Mode": "cors",
  "Sec-Fetch-Site": "same-origin",
};

// Same set the Python monitor models: only venues we can settle.
const ALLOWED_REGIONS = [
  "South Africa", "UK and Ireland", "Australia", "New Zealand", "USA",
  "Hong Kong", "Japan", "France", "United Arab Emirates", "UAE", "Bahrain",
];

export const RAW_DAILY_KEY = "betway:raw:daily";
export const RAW_CURSOR_KEY = "betway:raw:cursor";
export const RAW_SLOT_PREFIX = "betway:raw:slot:";
export const RAW_SLOTS = 16;
/** Events fetched per cron run (subrequests: 1 GetDaily + 30 GetEvent + puts). */
export const RAW_BATCH_SIZE = 30;
/** Races closest to post are refetched every run — they are the ones that move. */
const NEAR_OFF_COUNT = 14;
const SLOT_SIZE = 15;
const RAW_TTL_SECS = 3 * 3600;
const DAILY_REFRESH_EVERY = 3;

interface DailyEvent {
  eventId: number | string;
  isFinished?: boolean;
  expectedStartEpoch?: number;
  league?: string;
  leagueName?: string;
}

interface RaceRef {
  id: string;
  region: string;
  league: string;
  off: number;
}

export interface CronResult {
  ok: boolean;
  skipped?: boolean;
  daily: number;
  fetched: number;
  failed: number;
  slots: number[];
  next: number;
  error?: string;
}

async function betwayFetch(path: string, qs: string, timeoutMs = 20_000): Promise<Response | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(`${TRACK_API}/${path}?${qs}`, {
      headers: BETWAY_HEADERS,
      signal: controller.signal,
    });
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Race list, filtered to modelled regions, unfinished, earliest off-time first. */
export async function listRaces(): Promise<{ races: RaceRef[]; daily: unknown | null; error?: string }> {
  const dailyQs =
    "sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2";
  const res = await betwayFetch("GetDaily", dailyQs, 25_000);
  if (!res || res.status !== 200) {
    return { races: [], daily: null, error: `GetDaily HTTP ${res ? res.status : "no response"}` };
  }
  let payload: any;
  try {
    payload = await res.json();
  } catch {
    return { races: [], daily: null, error: "GetDaily returned non-JSON (Cloudflare block page?)" };
  }
  const races: RaceRef[] = [];
  for (const region of payload?.regions || []) {
    const regionName = String(region?.name || "");
    if (!ALLOWED_REGIONS.some((a) => regionName.includes(a))) continue;
    for (const ev of (region?.sportEvents || []) as DailyEvent[]) {
      if (ev?.isFinished) continue;
      const id = String(ev.eventId ?? "");
      if (!id) continue;
      races.push({
        id,
        region: regionName,
        league: String(ev?.league || ev?.leagueName || ""),
        off: Number(ev.expectedStartEpoch || 0),
      });
    }
  }
  // Soonest to post first: those prices are the ones that must be current.
  races.sort((a, b) => (a.off || 0) - (b.off || 0));
  return { races, daily: payload };
}

/** Fetch GetEvent payloads with bounded concurrency, keeping region/league. */
async function fetchEvents(
  refs: RaceRef[],
): Promise<{ events: Record<string, unknown>; failed: number }> {
  const events: Record<string, unknown> = {};
  let failed = 0;
  const queue = [...refs];

  const worker = async () => {
    while (queue.length) {
      const ref = queue.shift() as RaceRef;
      const qs = `eventIds=${encodeURIComponent(ref.id)}&marketGroupName=&countryCode=ZA`;
      const res = await betwayFetch("GetEvent", qs, 20_000);
      if (!res || res.status !== 200) {
        failed++;
        continue;
      }
      try {
        const payload = await res.json();
        // Region/league travel with the payload: the Python parser names the
        // course from them ("Unknown" otherwise), and there is no second
        // chance to look them up once the card is assembled.
        events[ref.id] = { payload, region: ref.region, league: ref.league };
      } catch {
        failed++;
      }
    }
  };

  await Promise.all([0, 1, 2, 3, 4].map(() => worker()));
  return { events, failed };
}

/**
 * One cron tick: refresh the races nearest to post, plus a rotating slice of
 * the rest, and park them in KV.
 */
export async function cronFetchBetway(env: CronEnv): Promise<CronResult> {
  const { races, daily, error } = await listRaces();
  if (!races.length) {
    return { ok: false, daily: 0, fetched: 0, failed: 0, slots: [], next: 0, error: error || "no unfinished races" };
  }

  let cursor: any = null;
  try {
    cursor = await env.ODDS_KV.get(RAW_CURSOR_KEY, "json");
  } catch {
    cursor = null;
  }
  const runNo = Number(cursor?.run_no ?? 0) + 1;
  const fails = Number(cursor?.fails ?? 0);

  // Stand-down (Nov-22): a blocked colo answers 403 every time, and hammering
  // it every 5 minutes only deepens the reputation problem with Betway. After
  // three consecutive failures, back off to every third run (~15 min) until a
  // run gets through again.
  if (fails >= 3 && runNo % 3 !== 0) {
    await env.ODDS_KV.put(
      RAW_CURSOR_KEY,
      JSON.stringify({ ...(cursor || {}), run_no: runNo, ts: new Date().toISOString() }),
      { expirationTtl: RAW_TTL_SECS },
    );
    return { ok: false, skipped: true, daily: 0, fetched: 0, failed: 0, slots: [], next: Number(cursor?.next ?? 0), error: "standing down after repeated blocks" };
  }

  const runs = Number(cursor?.runs ?? 0) + 1;

  // 14 soonest + the next 16 from the rotation. A cold registry still fills
  // within ~9 runs, while the races about to jump keep updating every run.
  const batch: RaceRef[] = races.slice(0, Math.min(NEAR_OFF_COUNT, races.length));
  const chosen = new Set(batch.map((r) => r.id));
  const start = Number(cursor?.next ?? 0) % races.length;
  for (let i = 0; batch.length < Math.min(RAW_BATCH_SIZE, races.length) && i < races.length; i++) {
    const ref = races[(start + i) % races.length];
    if (chosen.has(ref.id)) continue;
    chosen.add(ref.id);
    batch.push(ref);
  }
  const next = (start + RAW_BATCH_SIZE) % races.length;

  const { events, failed } = await fetchEvents(batch);
  const fetched = Object.keys(events).length;

  // Split into fixed-size slots so no single KV value approaches the 25 MB cap.
  const entries = Object.entries(events);
  const slots: number[] = [];
  let slotWrites = 0;
  for (let i = 0; i < entries.length; i += SLOT_SIZE) {
    const chunk = Object.fromEntries(entries.slice(i, i + SLOT_SIZE));
    const slot = Math.floor((start + i) / SLOT_SIZE) % RAW_SLOTS;
    // Only overwrite when something came back — a fully blocked run must not
    // replace a good slot with an empty one.
    await env.ODDS_KV.put(
      `${RAW_SLOT_PREFIX}${slot}`,
      JSON.stringify({ ts: new Date().toISOString(), events: chunk }),
      { expirationTtl: RAW_TTL_SECS },
    );
    slots.push(slot);
    slotWrites++;
  }

  if (daily && runs % DAILY_REFRESH_EVERY === 0) {
    await env.ODDS_KV.put(RAW_DAILY_KEY, JSON.stringify({ ts: new Date().toISOString(), daily }), {
      expirationTtl: RAW_TTL_SECS,
    });
  }

  await env.ODDS_KV.put(
    RAW_CURSOR_KEY,
    JSON.stringify({
      next,
      run_no: runNo,
      fails: fetched > 0 ? 0 : fails + 1,
      runs,
      ts: new Date().toISOString(),
      daily_count: races.length,
      fetched,
      failed,
      slots,
    }),
    { expirationTtl: RAW_TTL_SECS },
  );

  return {
    ok: fetched > 0,
    daily: races.length,
    fetched,
    failed,
    slots,
    next,
  };
}

// ── SportyBet fallback prices ─────────────────────────────────────────────
//
// SportyBet's Apollo gateway accepts Cloudflare edge egress but returns 403
// "Request blocked: ... violating security rules" from Modal's Azure range
// (verified 2026-11-25 with the same payload that returns 23 meetings from a
// residential IP). Modal also gets error 1010 from *.workers.dev, so there is
// no request/response bridge: this cron fetches on its own and parks a compact
// price table in KV, which Modal reads over api.cloudflare.com (reachable).
//
// KV budget: the Betway cron already writes ~960 values/day on the free tier's
// 1,000/day allowance. This writes at most once an hour with a 2h TTL.

export const SPORTYBET_PRICES_KEY = "sportybet:prices:v1";
const SPORTYBET_URL = "https://racing.sporty.bmapollo.com/query";
const SPORTYBET_HEADERS: Record<string, string> = {
  "content-type": "application/json",
  accept: "application/graphql-response+json, application/json",
  "x-api-key": "5kl1sj4d97mj623p1f04djhi1r",
  origin: "https://www.sportybet.co.za",
  referer: "https://www.sportybet.co.za/",
  "user-agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
};
const SPORTYBET_MIN_REFRESH_MS = 55 * 60_000;
const SPORTYBET_PRICES_TTL_SECS = 2 * 3600;
const SPORTYBET_CHUNK_SIZE = 15; // larger batches get "not authorized"

const MEETINGS_QUERY = `
  query m($s:Date!,$e:Date!) {
    meetingsBetween(startDate:$s,endDate:$e) {
      id track { name country } races { id number }
    }
  }
`;
const RACE_CARD_QUERY = `
  query raceCard($race_ids:[ID!]!) {
    meetingRaces(race_ids:$race_ids) {
      name track { name country }
      races {
        id number status start_at
        runners {
          id tab_no name status
          prices { bet_type price product { is_fixed } }
          runner_comments { comment updated_at }
        }
      }
    }
  }
`;

interface SBResult {
  ok: boolean;
  skipped?: boolean;
  events?: number;
  priced?: number;
  error?: string;
}

async function sbQuery(query: string, variables: Record<string, unknown>, op: string): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20_000);
  try {
    const res = await fetch(SPORTYBET_URL, {
      method: "POST",
      headers: SPORTYBET_HEADERS,
      body: JSON.stringify({ query, variables, operationName: op }),
      signal: controller.signal,
    });
    if (res.status !== 200) throw new Error(`HTTP ${res.status}`);
    const data: any = await res.json();
    if (data?.errors?.length) throw new Error(String(data.errors[0]?.message || "GraphQL error"));
    return data?.data || {};
  } finally {
    clearTimeout(timer);
  }
}

/** Fetch SportyBet prices from Cloudflare egress and park them in KV. */
export async function cronFetchSportyBet(env: CronEnv): Promise<SBResult> {
  try {
    const prev: any = await env.ODDS_KV.get(SPORTYBET_PRICES_KEY, "json");
    const last = Number(prev?.ts ? Date.parse(String(prev.ts)) : 0);
    if (last && Date.now() - last < SPORTYBET_MIN_REFRESH_MS) {
      return { ok: true, skipped: true };
    }

    const now = new Date();
    const day = now.toISOString().slice(0, 10);
    const s = `${day}T00:00:00Z`;
    const e = `${day}T23:59:59Z`;
    const meetings: any[] = (await sbQuery(MEETINGS_QUERY, { s, e }, "m")).meetingsBetween || [];
    if (!meetings.length) return { ok: false, error: "no meetings" };

    const ids: string[] = [];
    for (const m of meetings) {
      for (const r of m?.races || []) if (r?.id) ids.push(String(r.id));
    }
    if (!ids.length) return { ok: false, error: "no race ids" };

    const events: Record<string, unknown> = {};
    let priced = 0;
    for (let i = 0; i < ids.length; i += SPORTYBET_CHUNK_SIZE) {
      const chunk = ids.slice(i, i + SPORTYBET_CHUNK_SIZE);
      let data: any;
      try {
        data = await sbQuery(RACE_CARD_QUERY, { race_ids: chunk }, "raceCard");
      } catch {
        continue; // one throttled batch must not wipe the whole table
      }
      for (const meeting of data?.meetingRaces || []) {
        const country = String(meeting?.track?.country || "South Africa");
        const course = String(meeting?.track?.name || meeting?.name || "Unknown");
        for (const race of meeting?.races || []) {
          if (!race?.id) continue;
          const runners: Record<string, unknown>[] = [];
          for (const runner of race?.runners || []) {
            if (runner?.status === "SCRATCHED" || runner?.status === "WITHDRAWN") continue;
            const win = (runner?.prices || []).find(
              (p: any) => p?.product?.is_fixed && String(p?.bet_type || "").toLowerCase().includes("win"),
            );
            const odds = Number(win?.price || 0);
            if (odds > 1.0) priced++;
            const comments = (runner?.runner_comments || []).filter(
              (c: any) => String(c?.comment || "").trim(),
            );
            comments.sort((a: any, b: any) =>
              String(b?.updated_at || "").localeCompare(String(a?.updated_at || "")),
            );
            const tip = String(comments[0]?.comment || "").replace(/\s+/g, " ").slice(0, 300);
            runners.push({
              name: String(runner?.name || ""),
              odds: odds > 1.0 ? odds : "SP",
              topTip: tip,
            });
          }
          events[`sportybet_${race.id}`] = {
            course,
            en: `${country}: ${course}`,
            raceNumber: Number(race.number || 0),
            source: "sportybet",
            runners,
          };
        }
      }
    }

    if (!Object.keys(events).length) return { ok: false, error: "no racecards" };

    await env.ODDS_KV.put(
      SPORTYBET_PRICES_KEY,
      JSON.stringify({ ts: new Date().toISOString(), events, priced }),
      { expirationTtl: SPORTYBET_PRICES_TTL_SECS },
    );
    return { ok: true, events: Object.keys(events).length, priced };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}
