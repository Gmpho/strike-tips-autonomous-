// Minimal Cloudflare Pages/Workers runtime declarations for local typechecks.
// (Wrangler esbuilds without typechecking; these keep `tsc` honest.)
// Full types: `@cloudflare/workers-types` (not installed to avoid dep churn).

interface PagesFunction<Env = unknown> {
  (context: {
    request: Request;
    env: Env;
    params: Record<string, string | string[]>;
    waitUntil(promise: Promise<unknown>): void;
    passThroughOnException(): void;
    next(input?: RequestInfo | URL, init?: RequestInit): Promise<Response>;
    data: Record<string, unknown>;
  }): Response | Promise<Response>;
}

declare class WebSocketPair {
  0: WebSocket;
  1: WebSocket;
  [index: number]: WebSocket;
}

// Workers' server-side WebSocket has accept(); DOM lib type does not.
interface WebSocket {
  accept(): void;
}
