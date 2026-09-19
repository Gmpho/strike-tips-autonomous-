// Cloudflare Pages global middleware: proof-of-browser session issuance.
// Runs ahead of every Pages request. Lazy and cheap:
//  - requests already bearing a valid session token are passed through with
//    NO upstream call and NO new issuance;
//  - issuance happens only when the HUD explicitly asks for a session
//    (POST /api/session), or when an unauthenticated write arrives (in which
//    case we signal, not mint — minting requires the Turnstile challenge).
// The master backend key is NEVER named, read, or exposed here.

import { mint, verify, SESSION_TTL_SECS, SESSION_COOKIE_NAME } from "./lib/session.ts";

interface Env {
  SESSION_SECRET?: string;
  TURNSTILE_SECRET_KEY?: string;
  TURNSTILE_SITE_KEY?: string;
  SESSION_CHALLENGE_TTL_SECS?: string;
}

const CHALLENGE_TTL_SECS = 300; // Turnstile pass stays usable for 5 minutes
const challengeStore = new Map<string, { count: number; resetAt: number }>();
const ISSUE_WINDOW_MS = 60_000;
const ISSUE_MAX = 10; // token issuances/min per IP

export function cookieName(_env: Env): string {
  return SESSION_COOKIE_NAME;
}

// Present so the issuance branch can layer a skip-if-valid check on the
// session cookie without reaching back for another env read at call time;
// the hot path stays a cheap local signature check with no Turnstile call.
export function sessionSecret(env: Env): string {
  return env.SESSION_SECRET || "";
}

function readCookie(request: Request, name: string): string {
  const raw = request.headers.get("Cookie") || "";
  const parts = raw.split(";");
  for (const part of parts) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    if (part.slice(0, eq).trim() === name) return decodeURIComponent(part.slice(eq + 1).trim());
  }
  return "";
}

function setSessionCookie(token: string, name: string): string {
  return `${name}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=${SESSION_TTL_SECS}`;
}

function hitIssueLimit(ip: string): boolean {
  const now = Date.now();
  const entry = challengeStore.get(ip);
  if (!entry || now > entry.resetAt) {
    challengeStore.set(ip, { count: 1, resetAt: now + ISSUE_WINDOW_MS });
    return false;
  }
  entry.count++;
  return entry.count > ISSUE_MAX;
}

function ipOf(request: Request): string {
  return request.headers.get("cf-connecting-ip")
    || request.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || "unknown";
}

/** Validate a Turnstile token server-side. Never throws; `codes` carries the
 *  siteverify error-codes (or an http-<status> marker) for diagnostics.
 *  Fail-closed: a missing secret means no issuance. */
export async function verifyTurnstile(
  env: Env,
  token: string,
  ip: string,
): Promise<{ ok: boolean; codes: string[] }> {
  const secret = env.TURNSTILE_SECRET_KEY || "";
  if (!secret || !token) return { ok: false, codes: ["missing-secret-or-token"] };
  try {
    const form = new URLSearchParams({ secret, response: token, remoteip: ip });
    // NB: the documented siteverify endpoint is v0 (v1 returns 404 — found
    // via a live control probe, see restore-hud-write-path design notes).
    const res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) return { ok: false, codes: [`http-${res.status}`] };
    const data = (await res.json()) as { success?: boolean; "error-codes"?: unknown };
    const codes = Array.isArray(data["error-codes"])
      ? data["error-codes"].filter((c): c is string => typeof c === "string")
      : [];
    return { ok: data.success === true, codes };
  } catch {
    return { ok: false, codes: ["network-error"] };
  }
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);

  // Public config for the client: the Turnstile SITE key is public by design
  // (it ships in the HTML of every Turnstile-protected site), so serving it
  // from the edge keeps the client bundle free of build-time env — and means
  // rotating the key needs no rebuild. The SECRET key is never returned.
  if (url.pathname === "/api/session" && request.method === "GET") {
    const siteKey = env.TURNSTILE_SITE_KEY || "";
    return Response.json(
      { siteKey, enabled: Boolean(siteKey && env.SESSION_SECRET && env.TURNSTILE_SECRET_KEY), maxAgeSecs: SESSION_TTL_SECS },
      { status: 200, headers: { "Cache-Control": "public, max-age=300" } },
    );
  }

  // Session issuance endpoint: Turnstile-challenged POST mints the token
  // into an HttpOnly cookie. Only this path is answered here — everything
  // else flows straight to the per-route Functions below.
  if (url.pathname === "/api/session" && request.method === "POST") {
    const ip = ipOf(request);
    if (hitIssueLimit(ip)) {
      return Response.json({ error: "Too Many Requests" }, { status: 429, headers: { "Retry-After": "60" } });
    }
    const name = cookieName(env);
    const secret = sessionSecret(env);
    // Skip-if-valid: a caller already holding a live token needs no new one.
    // Cheap local signature check — no Turnstile call, no new issuance.
    if (secret) {
      const existing = await verify({ secret, token: readCookie(request, name) });
      if (existing) {
        return Response.json({ ok: true, reused: true, maxAgeSecs: SESSION_TTL_SECS }, { status: 200 });
      }
    }
    let token = "";
    try {
      const body = (await request.json()) as { turnstileToken?: unknown };
      token = typeof body.turnstileToken === "string" ? body.turnstileToken : "";
    } catch {
      return Response.json({ error: "Invalid JSON" }, { status: 400 });
    }
    const verdict = await verifyTurnstile(env, token, ip);
    if (!verdict.ok) {
      return Response.json({ error: "Challenge failed", codes: verdict.codes }, { status: 403 });
    }
    const session = await mint({ secret, challengePassed: true });
    if (!session) {
      // No SESSION_SECRET configured (or issuance disabled): fail closed.
      return Response.json({ error: "Sessions unavailable" }, { status: 503 });
    }
    return Response.json(
      { ok: true, maxAgeSecs: SESSION_TTL_SECS },
      { status: 200, headers: { "Set-Cookie": setSessionCookie(session, name) } },
    );
  }

  // Everything else flows through untouched. No upstream call, no secret
  // exposure, no latency added here — the per-route Functions run next.
  return context.next();
};
