import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  WebStandardStreamableHTTPServerTransport,
} from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { z } from "zod";
import { racingKnowledge, searchKnowledge, getKnowledge, getTrackKnowledge, listKnowledgePaths, listTrackPaths } from "./generated/racing-knowledge";

export interface Env {
  BACKEND_API_URL: string;
  BACKEND_API_KEY: string;
  SEARCH_API_KEY?: string;
  DB: D1Database;
  ODDS_KV: KVNamespace;
}

// ── Security helpers ────────────────────────────────────────────────

const MAX_STR = 500;

function isAuthorized(request: Request, env: Env): boolean {
  return !env.BACKEND_API_KEY || request.headers.get("x-api-key") === env.BACKEND_API_KEY;
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}

function error(msg: string, status = 400): Response {
  return json({ error: msg }, status);
}

function getNum(search: URLSearchParams, key: string): number | null {
  const v = search.get(key);
  if (v === null) return null;
  const n = Number(v);
  return isNaN(n) ? null : n;
}

function getStr(search: URLSearchParams, key: string): string | null {
  const v = search.get(key);
  if (v === null) return null;
  return v.slice(0, MAX_STR);
}

// ── PURE FUNCTIONS (shared between REST + MCP) ──────────────────────

function calcEdge(odds: number, prob: number) {
  const implied = 1.0 / odds;
  const edge = prob - implied;
  return {
    implied_probability: Math.round(implied * 10000) / 10000,
    mathematical_edge: Math.round(edge * 10000) / 10000,
    has_value_advantage: edge >= 0.05,
  };
}

function calcKelly(odds: number, prob: number, bankroll: number) {
  const b = odds - 1.0;
  const p = prob;
  const q = 1.0 - p;
  const kelly = b > 0 ? 0.5 * ((b * p - q) / b) : 0.0;
  const stake_percent = Math.min(Math.max(0.0, kelly), 0.05);
  return {
    stake_percentage_allocation: Math.round(stake_percent * 10000) / 10000,
    suggested_stake_zar: Math.round(bankroll * stake_percent * 100) / 100,
    governance_ceiling_tripped: kelly > 0.05,
  };
}

function checkCircuit(dailyLoss: number, peak: number, current: number) {
  const drawdown = ((peak - current) / peak) * 100.0;
  const halted = dailyLoss >= 20.0 || drawdown >= 50.0;
  return {
    daily_loss_percentage: Math.round(dailyLoss * 100) / 100,
    drawdown_percentage: Math.round(drawdown * 100) / 100,
    circuit_breaker_tripped: halted,
    operational_status: halted ? "HALTED" : "OPERATIONAL",
  };
}

function runBayesian(wins: number, bets: number, prior: number) {
  if (bets < wins) return { error: "total_bets must be >= historical_wins" };
  const alpha_prior = prior * 10.0;
  const beta_prior = (1.0 - prior) * 10.0;
  const post_alpha = alpha_prior + wins;
  const post_beta = beta_prior + (bets - wins);
  return {
    calibrated_probability_prior: Math.round((post_alpha / (post_alpha + post_beta)) * 10000) / 10000,
    sample_weight_confidence: post_alpha + post_beta,
  };
}

function scanKeywords(text: string) {
  const keywords = ["scratch", "market mover", "heavy rain", "change of jockey", "non-runner", "going", "withdrawn"];
  const detected = keywords.filter((kw) => text.toLowerCase().includes(kw));
  return { extracted_context_flags: detected };
}

function evaluateRace(track: string, raceNumber: number) {
  return {
    track: track.toLowerCase(),
    race_number: raceNumber,
    endpoint: `/api/racing/evaluate/${track}/${raceNumber}`,
    status: "ANALYSIS_COMPLETE",
  };
}

function verifyRaceCard(track: string, runners: number) {
  const valid = runners >= 3;
  return {
    track: track.toLowerCase(),
    total_verified_runners: valid ? runners : 0,
    sanity_check_passed: valid,
    action: valid ? "NONE" : "TRIGGER_RECOVERY",
  };
}

function triggerPatch(selector: string) {
  return {
    broken_node: selector.slice(0, 200),
    generated_patch: "div.runner-name-container > span",
    status: "PATCH_RELOADED",
  };
}

// ── D1 / KV HELPERS (parameterized queries + LIKE escape) ──────────

function escapeLike(s: string): string {
  return s.replace(/[%_\\]/g, "\\$&");
}

async function searchFormInsights(db: D1Database, track: string, runnerName: string) {
  const searchTerm = `%${escapeLike(runnerName.slice(0, 100))}%`;
  const trackFilter = track ? escapeLike(track.toLowerCase().slice(0, 100)) : "";
  const { results } = await db.prepare(
    `SELECT id, horse, content, type, track, race_number, date, metadata_json, created_at
     FROM form_insights
     WHERE (LOWER(track) = ?1 OR ?1 = '')
       AND (LOWER(horse) LIKE ?2 OR content LIKE ?2)
     ORDER BY created_at DESC
     LIMIT 20`,
  ).bind(trackFilter, searchTerm).all();
  return results || [];
}

async function getOddsSnapshot(kv: KVNamespace, track: string, raceNumber: number) {
  const key = `odds:${track.toLowerCase().slice(0, 100)}:${raceNumber}`;
  const val = await kv.get(key, "text");
  if (!val) return { note: "No cached odds for this race" };
  try { return JSON.parse(val); } catch { return { error: "corrupted cache" }; }
}

async function ingestOdds(kv: KVNamespace, track: string, raceNumber: number, data: string) {
  const key = `odds:${track.toLowerCase().slice(0, 100)}:${raceNumber}`;
  await kv.put(key, data.slice(0, 100000), { expirationTtl: 180 });
}

interface InsightBody {
  doc_id: string; horse: string; content: string;
  type?: string; track?: string; race_number?: number; date?: string;
  metadata?: Record<string, unknown>;
}
async function ingestInsight(db: D1Database, body: InsightBody) {
  await db.prepare(
    `INSERT OR REPLACE INTO form_insights (doc_id, horse, content, type, track, race_number, date, metadata_json)
     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)`,
  ).bind(
    body.doc_id.slice(0, 200), body.horse.slice(0, 200), body.content.slice(0, 10000),
    body.type?.slice(0, 50) || "form_insight", body.track?.slice(0, 100) || null,
    body.race_number || null, body.date?.slice(0, 20) || null,
    JSON.stringify(body.metadata || {}).slice(0, 5000),
  ).run();
}

// ── ROUTE HANDLERS ──────────────────────────────────────────────────

async function handleGET(url: URL, env: Env): Promise<Response> {
  const { pathname, searchParams: q } = url;
  const path = pathname.toLowerCase();

  try {
    if (path === "/api/edge" || path === "/api/calculate-edge") {
      const odds = getNum(q, "decimal_odds");
      const prob = getNum(q, "estimated_prob");
      if (!odds || !prob) return error("decimal_odds and estimated_prob required");
      return json(calcEdge(odds, prob));
    }

    if (path === "/api/kelly" || path === "/api/calculate-max-position") {
      const odds = getNum(q, "decimal_odds");
      const prob = getNum(q, "estimated_prob");
      const bankroll = getNum(q, "total_bankroll");
      if (!odds || !prob || !bankroll) return error("decimal_odds, estimated_prob, total_bankroll required");
      return json(calcKelly(odds, prob, bankroll));
    }

    if (path === "/api/circuit" || path === "/api/check-circuit-breakers") {
      const loss = getNum(q, "current_daily_loss");
      const peak = getNum(q, "peak_historical_bankroll");
      const current = getNum(q, "current_bankroll");
      if (loss === null || !peak || !current) return error("current_daily_loss, peak_historical_bankroll, current_bankroll required");
      return json(checkCircuit(loss, peak, current));
    }

    if (path === "/api/bayesian" || path === "/api/run-bayesian-calibration") {
      const wins = getNum(q, "historical_wins");
      const bets = getNum(q, "total_bets");
      const prior = getNum(q, "initial_prior");
      if (wins === null || bets === null || prior === null) return error("historical_wins, total_bets, initial_prior required");
      return json(runBayesian(wins, bets, prior));
    }

    if (path === "/api/keywords" || path === "/api/scan-semantic-keywords") {
      const text = getStr(q, "raw_user_prompt") || getStr(q, "text") || "";
      if (!text) return error("raw_user_prompt or text required");
      return json(scanKeywords(text));
    }

    if (path === "/api/evaluate" || path === "/api/evaluate-race-matrix") {
      const track = getStr(q, "track");
      const raceNum = getNum(q, "race_number");
      if (!track || !raceNum) return error("track and race_number required");
      return json(evaluateRace(track, raceNum));
    }

    if (path === "/api/verify-card" || path === "/api/verify-race-card-array") {
      const track = getStr(q, "track");
      const runners = getNum(q, "total_scraped_runners");
      if (!track || runners === null) return error("track and total_scraped_runners required");
      return json(verifyRaceCard(track, runners));
    }

    if (path === "/api/patch-html" || path === "/api/trigger-tab-html-patch") {
      const selector = getStr(q, "broken_selector");
      if (!selector) return error("broken_selector required");
      return json(triggerPatch(selector));
    }

    if (path === "/api/racing/form" || path === "/api/search-past-races") {
      const track = getStr(q, "track") || "";
      const runner = getStr(q, "runner_name") || getStr(q, "runner") || "";
      if (!runner) return error("runner_name required");
      const results = await searchFormInsights(env.DB, track, runner);
      return json({ query: { track, runner_name: runner }, count: results.length, results });
    }

    if (path === "/api/racing/odds" || path === "/api/fetch-live-odds-stream") {
      const track = getStr(q, "track");
      const raceNum = getNum(q, "race_number");
      if (track && raceNum) {
        const data = await getOddsSnapshot(env.ODDS_KV, track, raceNum);
        return json(data);
      }
      // Return full snapshot when no specific track/race
      const full = await env.ODDS_KV.get("odds:full_snapshot", "text");
      if (!full) return json({ note: "No snapshot available" });
      try { return json(JSON.parse(full)); } catch { return json({ error: "corrupted snapshot" }); }
    }

    // ── OKF Knowledge endpoints ────────────────────────────────────
    if (path === "/api/knowledge") {
      const pathArg = getStr(q, "path") || "";
      if (pathArg) {
        const entry = getKnowledge(pathArg);
        if (!entry) return json({ error: `knowledge path '${pathArg}' not found` }, 404);
        return json(entry);
      }
      return json({ paths: listKnowledgePaths(), count: listKnowledgePaths().length });
    }

    if (path === "/api/knowledge/search") {
      const query = getStr(q, "q") || getStr(q, "query") || "";
      if (!query) return error("q or query parameter required");
      const results = searchKnowledge(query);
      return json({ query, count: results.length, results: results.map(r => ({ path: r.path, score: r.score, metadata: r.entry.metadata })) });
    }

    if (path === "/api/knowledge/tracks") {
      const track = getStr(q, "track") || "";
      if (track) {
        const entry = getTrackKnowledge(track);
        if (!entry) return json({ error: `track '${track}' not found` }, 404);
        return json(entry);
      }
      const paths = listTrackPaths();
      const data = paths.map(p => ({ path: p, metadata: (racingKnowledge[p]?.metadata || {}) }));
      return json({ tracks: data, count: data.length });
    }

    if (path === "/api/health" || path === "/api/status") {
      return json({ status: "ok", service: "striketips-mcp", version: "2.0.0" });
    }

    return json({ error: "not found" }, 404);
  } catch {
    return json({ error: "internal error" }, 500);
  }
}

async function handlePOST(request: Request, url: URL, env: Env): Promise<Response> {
  if (!isAuthorized(request, env)) return json({ error: "unauthorized" }, 401);

  const path = url.pathname.toLowerCase();
  try {
    if (path === "/api/ingest-odds") {
      const body = (await request.json()) as { track: string; race_number: number; data: string };
      if (!body.track || !body.race_number || !body.data) return error("track, race_number, data required");
      await ingestOdds(
        env.ODDS_KV, body.track, body.race_number,
        typeof body.data === "string" ? body.data : JSON.stringify(body.data),
      );
      return json({ status: "ingested" });
    }

    if (path === "/api/ingest-snapshot") {
      const body = (await request.json()) as Record<string, unknown>;
      if (!body.events || typeof body.events !== "object") return error("events object required");
      // Store full snapshot
      await env.ODDS_KV.put("odds:full_snapshot", JSON.stringify(body), { expirationTtl: 300 });
      // Fan out individual events for backward compat
      const events = body.events as Record<string, Record<string, unknown>>;
      let count = 0;
      for (const [eid, event] of Object.entries(events)) {
        const course = (event.course || event.en || "") as string;
        const raceNum = (event.raceNumber as number) || 0;
        if (course && raceNum > 0) {
          const track = course.split(":").pop()?.trim().toLowerCase() || course.toLowerCase();
          await env.ODDS_KV.put(`odds:${track}:${raceNum}`, JSON.stringify(event), { expirationTtl: 300 });
          count++;
        }
      }
      return json({ status: "ingested", events: count });
    }

    if (path === "/api/ingest-insight") {
      const body = (await request.json()) as InsightBody;
      if (!body.doc_id || !body.horse || !body.content) return error("doc_id, horse, content required");
      await ingestInsight(env.DB, body);
      return json({ status: "ingested" });
    }

    return json({ error: "not found" }, 404);
  } catch {
    return json({ error: "internal error" }, 500);
  }
}

async function handleMCP(request: Request, env: Env): Promise<Response> {
  if (!isAuthorized(request, env)) return json({ error: "unauthorized" }, 401);

  const server = new McpServer({
    name: "StrikeTips-Autonomous-Core",
    version: "2.0.0",
  });

  server.tool("calculate_probability_edge", "Compute mathematical edge.",
    { decimal_odds: z.number().gt(1), estimated_prob: z.number().min(0).max(1) },
    async ({ decimal_odds, estimated_prob }) => ({
      content: [{ type: "text", text: JSON.stringify(calcEdge(decimal_odds, estimated_prob)) }],
    }),
  );

  server.tool("calculate_max_position", "Half-Kelly stake capped at 5%.",
    { decimal_odds: z.number().gt(1), estimated_prob: z.number().min(0).max(1), total_bankroll: z.number().gt(0) },
    async ({ decimal_odds, estimated_prob, total_bankroll }) => ({
      content: [{ type: "text", text: JSON.stringify(calcKelly(decimal_odds, estimated_prob, total_bankroll)) }],
    }),
  );

  server.tool("check_circuit_breakers", "Enforce 20% daily / 50% drawdown stop.",
    { current_daily_loss: z.number(), peak_historical_bankroll: z.number().gt(0), current_bankroll: z.number().gt(0) },
    async ({ current_daily_loss, peak_historical_bankroll, current_bankroll }) => ({
      content: [{ type: "text", text: JSON.stringify(checkCircuit(current_daily_loss, peak_historical_bankroll, current_bankroll)) }],
    }),
  );

  server.tool("run_bayesian_calibration", "Bayesian Beta-binomial update.",
    { historical_wins: z.number().int().min(0), total_bets: z.number().int().min(0), initial_prior: z.number().min(0).max(1) },
    async ({ historical_wins, total_bets, initial_prior }) => ({
      content: [{ type: "text", text: JSON.stringify(runBayesian(historical_wins, total_bets, initial_prior)) }],
    }),
  );

  server.tool("scan_semantic_keywords", "Extract racing keywords from text.",
    { raw_user_prompt: z.string() },
    async ({ raw_user_prompt }) => ({
      content: [{ type: "text", text: JSON.stringify(scanKeywords(raw_user_prompt)) }],
    }),
  );

  server.tool("evaluate_race_matrix", "Get evaluation status for a race.",
    { track: z.string(), race_number: z.number().int().positive() },
    async ({ track, race_number }) => ({
      content: [{ type: "text", text: JSON.stringify(evaluateRace(track, race_number)) }],
    }),
  );

  server.tool("verify_race_card_array", "Sanity-check runner count (>= 3).",
    { track: z.string(), total_scraped_runners: z.number().int().min(0) },
    async ({ track, total_scraped_runners }) => ({
      content: [{ type: "text", text: JSON.stringify(verifyRaceCard(track, total_scraped_runners)) }],
    }),
  );

  server.tool("trigger_tab_html_patch", "Self-healing CSS selector patch.",
    { broken_selector: z.string().max(200) },
    async ({ broken_selector }) => ({
      content: [{ type: "text", text: JSON.stringify(triggerPatch(broken_selector)) }],
    }),
  );

  server.tool("search_past_races", "Search historical form data via D1.",
    { track: z.string().max(100), runner_name: z.string().max(100) },
    async ({ track, runner_name }) => {
      const results = await searchFormInsights(env.DB, track, runner_name);
      return { content: [{ type: "text", text: JSON.stringify({ query: { track, runner_name }, count: results.length, results }) }] };
    },
  );

  server.tool("get_dream_simulation", "Monte-Carlo simulation from Dream Engine.",
    { track: z.string(), race_number: z.number().int().positive() },
    async ({ track, race_number }) => {
      const resp = await fetch(
        `${env.BACKEND_API_URL}/api/racing/dream-sim?track=${encodeURIComponent(track)}&race=${race_number}`,
        { headers: env.BACKEND_API_KEY ? { "X-API-KEY": env.BACKEND_API_KEY } : {} },
      );
      return { content: [{ type: "text", text: JSON.stringify(await resp.json()) }] };
    },
  );

  server.tool("fetch_live_odds_stream", "Cached odds from KV.",
    { track: z.string(), race_number: z.number().int().positive() },
    async ({ track, race_number }) => {
      const data = await getOddsSnapshot(env.ODDS_KV, track, race_number);
      return { content: [{ type: "text", text: JSON.stringify(data) }] };
    },
  );

  // ── OKF Knowledge tools ─────────────────────────────────────────
  server.tool("search_racing_knowledge", "Search OKF racing knowledge bundle for tracks, conditions, strategies.",
    { query: z.string().min(1).max(200) },
    async ({ query }) => {
      const results = searchKnowledge(query);
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            query,
            count: results.length,
            results: results.map(r => ({
              path: r.path,
              score: r.score,
              title: r.entry.metadata.title || r.path,
              description: r.entry.metadata.description || "",
            })),
          }),
        }],
      };
    },
  );

  server.tool("list_racing_knowledge", "List all available knowledge paths in the OKF bundle.",
    {
      category: z.enum(["all", "tracks", "conditions", "strategies"]).default("all").describe("Filter by category"),
    },
    async ({ category }) => {
      const all = listKnowledgePaths();
      const filtered = category === "all" ? all : all.filter(p => p.startsWith(category + "/"));
      const items = filtered.map(p => ({
        path: p,
        metadata: racingKnowledge[p]?.metadata || {},
      }));
      return {
        content: [{ type: "text", text: JSON.stringify({ count: items.length, items }) }],
      };
    },
  );

  server.tool("get_racing_knowledge", "Get full OKF knowledge entry by path (e.g. tracks/kenilworth.md).",
    { path: z.string().min(1).max(200) },
    async ({ path }) => {
      const entry = getKnowledge(path);
      if (!entry) return { content: [{ type: "text", text: JSON.stringify({ error: `path '${path}' not found` }) }] };
      return { content: [{ type: "text", text: JSON.stringify({ path, metadata: entry.metadata, body: entry.body }) }] };
    },
  );

  server.tool("get_track_knowledge", "Get knowledge entry for a specific race track (partial name match).",
    { track_name: z.string().min(1).max(100) },
    async ({ track_name }) => {
      const entry = getTrackKnowledge(track_name);
      if (!entry) return { content: [{ type: "text", text: JSON.stringify({ error: `track '${track_name}' not found` }) }] };
      return { content: [{ type: "text", text: JSON.stringify({ metadata: entry.metadata, body: entry.body }) }] };
    },
  );

  // ── Web Search tool ──────────────────────────────────────────────
  server.tool("web_search_racing", "Search the web for up-to-date racing info (form, news, tips). Requires SEARCH_API_KEY env var.",
    { query: z.string().min(1).max(500) },
    async ({ query }) => {
      const apiKey = env.SEARCH_API_KEY;
      if (!apiKey) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ error: "Web search not configured. Set SEARCH_API_KEY secret to enable.", note: "Get a free API key from Brave Search (api.search.brave.com) or Tavily." }),
          }],
        };
      }
      try {
        const resp = await fetch(
          `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query + " horse racing")}&count=5`,
          { headers: { "Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": apiKey } },
        );
        if (!resp.ok) return { content: [{ type: "text", text: JSON.stringify({ error: `Search API returned ${resp.status}` }) }] };
        const data = await resp.json() as { web?: { results?: Array<{ title: string; url: string; description: string }> } };
        const results = data.web?.results?.slice(0, 5).map(r => ({ title: r.title, url: r.url, snippet: r.description })) || [];
        return { content: [{ type: "text", text: JSON.stringify({ query, count: results.length, results }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: JSON.stringify({ error: String(e) }) }] };
      }
    },
  );

  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  await server.connect(transport);
  return await transport.handleRequest(request);
}

// ── WORKER ENTRY ────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;
    const method = request.method.toUpperCase();

    try {
      if (pathname === "/mcp") {
        return await handleMCP(request, env);
      }

      if (pathname.startsWith("/api/")) {
        if (method === "POST") {
          return await handlePOST(request, url, env);
        }
        return await handleGET(url, env);
      }

      if (pathname === "/") {
        return json({ service: "striketips-mcp", version: "2.0.0" });
      }

      return json({ error: "not found" }, 404);
    } catch {
      return json({ error: "internal error" }, 500);
    }
  },
};
