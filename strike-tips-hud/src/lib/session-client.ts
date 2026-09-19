// Proof-of-browser session bootstrap (client half).
// The Turnstile SITE key is fetched from the edge at call time (GET
// /api/session) rather than read from build-time env. Two reasons:
//   1. A build-time-only key lets the bundler constant-fold this whole
//      module away when the key is absent (observed: a 132-byte chunk that
//      just `return false`), so an already-deployed bundle could never work.
//   2. Rotating the key then needs no rebuild/redeploy.
// Only the site key is public; the secret stays server-side.

interface SessionConfig {
  siteKey: string;
  enabled: boolean;
}

let configPromise: Promise<SessionConfig> | null = null;

function loadConfig(): Promise<SessionConfig> {
  if (configPromise) return configPromise;
  configPromise = (async () => {
    try {
      const res = await fetch("/api/session", { method: "GET", credentials: "same-origin" });
      if (!res.ok) return { siteKey: "", enabled: false };
      const body = (await res.json()) as { siteKey?: unknown; enabled?: unknown };
      return {
        siteKey: typeof body.siteKey === "string" ? body.siteKey : "",
        enabled: body.enabled === true,
      };
    } catch {
      return { siteKey: "", enabled: false };
    } finally {
      // Allow a later attempt (e.g. after the edge is reconfigured).
      setTimeout(() => { configPromise = null; }, 60_000);
    }
  })();
  return configPromise;
}

interface TurnstileApi {
  render(el: HTMLElement, opts: Record<string, unknown>): string;
  remove(id: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<void> | null = null;

function loadTurnstile(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  if (window.turnstile) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    s.async = true;
    s.dataset.turnstile = "bootstrap";
    s.onload = () => (window.turnstile ? resolve() : reject(new Error("turnstile missing")));
    s.onerror = () => reject(new Error("turnstile script failed"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

function renderChallenge(siteKey: string): Promise<string | null> {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.6)";
    const box = document.createElement("div");
    box.style.cssText = "padding:24px;border-radius:16px;background:#171225;box-shadow:0 0 40px rgba(0,0,0,.5)";
    const slot = document.createElement("div");
    box.appendChild(slot);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    let done = false;
    const finish = (token: string | null) => {
      if (done) return;
      done = true;
      try {
        const id = overlay.dataset.widgetId;
        if (id && window.turnstile) window.turnstile.remove(id);
      } catch { /* already gone */ }
      overlay.remove();
      resolve(token);
    };
    try {
      const id = window.turnstile!.render(slot, {
        sitekey: siteKey,
        callback: (t: string) => finish(t),
        "error-callback": () => finish(null),
        "expire-callback": () => finish(null),
        timeout: 120_000,
      });
      overlay.dataset.widgetId = String(id);
    } catch {
      finish(null);
    }
  });
}

let inflight: Promise<boolean> | null = null;

/** Run the Turnstile challenge and exchange it for a session cookie.
 *  Resolves true only when the server accepted the challenge and set the
 *  cookie; false on every other path (no key configured, challenge failed,
 *  issuance 4xx/5xx). Never throws. */
export async function ensureSession(): Promise<boolean> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const { siteKey, enabled } = await loadConfig();
      if (!siteKey || !enabled) return false;
      await loadTurnstile();
      const challenge = await renderChallenge(siteKey);
      if (!challenge) return false;
      const res = await fetch("/api/session", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ turnstileToken: challenge }),
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}
