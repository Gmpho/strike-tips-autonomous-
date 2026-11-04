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
    let widgetId = "";
    const finish = (token: string | null) => {
      if (done) return;
      done = true;
      try {
        if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
      } catch { /* already gone */ }
      overlay.remove();
      resolve(token);
    };
    // Explicit verification-failed state: the overlay STAYS MOUNTED with a
    // retry affordance instead of silently closing (harden-pages-functions
    // 3.2 — the 600010 silent-close UX bug). Cancel is always available.
    const showFailed = (msg: string) => {
      box.textContent = "";
      const label = document.createElement("div");
      label.textContent = msg;
      label.style.cssText = "color:#f87171;font-size:14px;margin-bottom:12px;font-family:system-ui,sans-serif";
      const row = document.createElement("div");
      row.style.cssText = "display:flex;gap:8px";
      const retry = document.createElement("button");
      retry.textContent = "Retry verification";
      retry.style.cssText = "padding:8px 14px;border-radius:8px;background:#7c3aed;color:#fff;border:0;cursor:pointer;font-family:system-ui,sans-serif";
      retry.onclick = () => {
        // In-place reset: re-render the widget into the same overlay.
        box.textContent = "";
        box.appendChild(slot);
        try { if (widgetId && window.turnstile) window.turnstile.remove(widgetId); } catch { /* noop */ }
        try {
          widgetId = window.turnstile!.render(slot, opts);
          overlay.dataset.widgetId = String(widgetId);
        } catch {
          showFailed("Verification could not start. You can retry.");
        }
      };
      const cancel = document.createElement("button");
      cancel.textContent = "Cancel";
      cancel.style.cssText = "padding:8px 14px;border-radius:8px;background:transparent;color:#94a3b8;border:1px solid #334155;cursor:pointer;font-family:system-ui,sans-serif";
      cancel.onclick = () => finish(null);
      row.appendChild(retry);
      row.appendChild(cancel);
      box.appendChild(label);
      box.appendChild(row);
    };
    const opts = {
      sitekey: siteKey,
      callback: (t: string) => finish(t),
      "error-callback": () => showFailed("Verification failed. You can retry."),
      "expire-callback": () => showFailed("Verification expired. You can retry."),
      "timeout-callback": () => showFailed("Verification timed out. You can retry."),
      timeout: 120_000,
    };
    try {
      widgetId = window.turnstile!.render(slot, opts);
      overlay.dataset.widgetId = String(widgetId);
    } catch {
      showFailed("Verification could not start. You can retry.");
    }
  });
}

let inflight: Promise<SessionOutcome> | null = null;

export type SessionOutcome = "ok" | "challenge-failed" | "unavailable";

/** Run the Turnstile challenge and exchange it for a session cookie.
 *  Resolves "ok" only when the server accepted the challenge and set the
 *  cookie; "challenge-failed" when the challenge itself failed, expired,
 *  timed out, or the user dismissed it; "unavailable" when sessions are not
 *  configured or the network/bootstrap path failed. Never throws. */
export async function ensureSession(): Promise<SessionOutcome> {
  if (inflight) return inflight;
  inflight = (async (): Promise<SessionOutcome> => {
    try {
      const { siteKey, enabled } = await loadConfig();
      if (!siteKey || !enabled) return "unavailable";
      await loadTurnstile();
      const challenge = await renderChallenge(siteKey);
      if (!challenge) return "challenge-failed";
      const res = await fetch("/api/session", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ turnstileToken: challenge }),
      });
      return res.ok ? "ok" : "challenge-failed";
    } catch {
      return "unavailable";
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}
