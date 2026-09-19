// strike-tips-hud/functions/lib/session.ts
// Proof-of-browser session helpers — PURE module.
//
// Uses only WebCrypto (`crypto.subtle`, `crypto.getRandomValues`) and
// TextEncoder/TextDecoder. No imports of any kind, so this file is safe to
// unit-test with Node's built-in runner and to ship inside Pages Functions.
// Erasable-syntax only (no enums/namespaces/classes) so Node type-stripping
// runs it directly.
//
// Token shape: base64url(JSON claims) + "." + base64url(HMAC-SHA256(secret, claims)).

export const SESSION_AUD = "hud-write";
export const SESSION_TTL_SECS = 15 * 60;
export const CLOCK_SKEW_SECS = 60;
export const SESSION_VERSION = 1;
export const SESSION_COOKIE_NAME = "st_session";

export interface SessionClaims {
  v: number;
  aud: string;
  iat: number;
  exp: number;
  jti: string;
}

export interface MintOptions {
  secret: string;
  aud?: string;
  ttlSecs?: number;
  nowSecs?: number;
  jti?: string;
  challengePassed: boolean;
}

export interface VerifyOptions {
  secret: string;
  token: string;
  aud?: string;
  nowSecs?: number;
}

const enc = new TextEncoder();
const dec = new TextDecoder();

export function base64urlEncode(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function base64urlDecode(s: string): Uint8Array<ArrayBuffer> | null {
  let b64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4;
  if (pad === 1) return null;
  if (pad) b64 += "=".repeat(4 - pad);
  try {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch {
    return null;
  }
}

function randomJti(): string {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

async function hmacKey(secret: string): Promise<CryptoKey | null> {
  if (!secret) return null;
  try {
    return await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  } catch {
    return null;
  }
}

function constantTimeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

/** Mint a session token. Returns null unless the Turnstile challenge passed
 *  (issuance gating lives here as pure logic; the siteverify call itself is
 *  the middleware's job). Fail-closed on empty secret. */
export async function mint(opts: MintOptions): Promise<string | null> {
  if (!opts || !opts.challengePassed) return null;
  const secret = opts.secret || "";
  const aud = opts.aud ?? SESSION_AUD;
  const ttl = opts.ttlSecs ?? SESSION_TTL_SECS;
  const now = opts.nowSecs ?? Math.floor(Date.now() / 1000);
  if (!aud || ttl <= 0) return null;
  const key = await hmacKey(secret);
  if (!key) return null;
  const claims: SessionClaims = { v: SESSION_VERSION, aud, iat: now, exp: now + ttl, jti: opts.jti ?? randomJti() };
  const payload = enc.encode(JSON.stringify(claims));
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, payload));
  return base64urlEncode(payload) + "." + base64urlEncode(sig);
}

function isClaims(x: unknown): x is SessionClaims {
  if (typeof x !== "object" || x === null) return false;
  const c = x as Record<string, unknown>;
  return c.v === SESSION_VERSION
    && typeof c.aud === "string"
    && typeof c.iat === "number"
    && typeof c.exp === "number"
    && typeof c.jti === "string";
}

/** Verify a session token. Returns the claims on success, null on any
 *  failure (malformed, bad signature, wrong audience, expired, issued in
 *  the future beyond clock skew, empty secret). */
export async function verify(opts: VerifyOptions): Promise<SessionClaims | null> {
  const secret = opts?.secret || "";
  const token = opts?.token || "";
  const aud = opts?.aud ?? SESSION_AUD;
  const now = opts?.nowSecs ?? Math.floor(Date.now() / 1000);
  const dot = token.indexOf(".");
  if (dot < 1) return null;
  const payloadBytes = base64urlDecode(token.slice(0, dot));
  const sigBytes = base64urlDecode(token.slice(dot + 1));
  if (!payloadBytes || !sigBytes) return null;
  const key = await hmacKey(secret);
  if (!key) return null;
  const expected = new Uint8Array(await crypto.subtle.sign("HMAC", key, payloadBytes));
  if (!constantTimeEqual(expected, sigBytes)) return null;
  let claims: unknown;
  try {
    claims = JSON.parse(dec.decode(payloadBytes));
  } catch {
    return null;
  }
  if (!isClaims(claims)) return null;
  if (claims.aud !== aud) return null;
  if (claims.exp <= now) return null;
  if (claims.iat > now + CLOCK_SKEW_SECS) return null;
  return claims;
}

// Boundary-aware prefix matching — MUST agree with
// functions/api/[[catchall]].ts's local helper (kept byte-identical on
// purpose: the trailing-slash boundary behaviour is fixed by the sibling
// harden-pages-functions change, not here).
export function matches(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(prefix.endsWith("/") ? prefix : prefix + "/");
}

export const SESSION_WRITE_PREFIXES = ["/api/config", "/api/healing/", "/api/dreaming/"];
export const MASTER_ONLY_PREFIXES = ["/api/agent/kill", "/api/agent/reset"];

/** True when a session token (proof-of-browser) may satisfy this path.
 *  Sensitive actions are excluded first and independently, so token
 *  acceptance can never broaden to them by accident. */
export function scopeAllows(path: string): boolean {
  if (MASTER_ONLY_PREFIXES.some((p) => matches(path, p))) return false;
  return SESSION_WRITE_PREFIXES.some((p) => matches(path, p));
}
