/**
 * Tiny request/response layer over module-singleton Web Workers.
 * One pattern for sentiment/TTS/translation/TrOCR: id-correlated calls with
 * timeouts, shared worker instances, progress fan-out. Failures resolve
 * null — callers decide what (if anything) to render.
 */

interface Pending {
  resolve: (msg: any) => void;
}

const workers = new Map<string, Worker>();
const booting = new Map<string, Promise<Worker | null>>();
const pending = new Map<number, Pending>();
let msgId = 0;

type ProgressFn = (progress: number, text: string) => void;

function attach(worker: Worker, onProgress?: ProgressFn): void {
  worker.onmessage = (e: MessageEvent) => {
    const msg = e.data ?? {};
    if (msg.type === 'PROGRESS') {
      onProgress?.(msg.progress ?? 0, msg.text ?? '');
      return;
    }
    if (typeof msg.id === 'number' && pending.has(msg.id)) {
      const p = pending.get(msg.id)!;
      pending.delete(msg.id);
      p.resolve(msg);
    }
  };
  worker.onerror = () => {
    for (const p of pending.values()) p.resolve({ type: 'ERROR' });
    pending.clear();
  };
}

export function getSharedWorker(
  key: string,
  // NOTE: pass a `() => new XxxWorker()` closure where XxxWorker comes from
  // a static `?worker` import. Vite only emits worker chunks for statically
  // analyzable constructors — a `new URL()` passed through a helper is left
  // as a dead runtime URL and the worker 404s.
  makeWorker: () => Worker,
  onProgress?: ProgressFn
): Promise<Worker | null> {
  const existing = workers.get(key);
  if (existing) return Promise.resolve(existing);
  const inflight = booting.get(key);
  if (inflight) return inflight;
  const p = (async (): Promise<Worker | null> => {
    try {
      const w = makeWorker();
      attach(w, onProgress);
      workers.set(key, w);
      return w;
    } catch {
      return null;
    } finally {
      booting.delete(key);
    }
  })();
  booting.set(key, p);
  return p;
}

export function dropSharedWorker(key: string): void {
  const w = workers.get(key);
  if (w) {
    try {
      w.terminate();
    } catch {}
    workers.delete(key);
  }
}

/** Post a message and await the correlated reply (default 90s). */
export function callWorker<T>(
  worker: Worker,
  message: Record<string, unknown>,
  timeoutMs = 90000,
  transfer?: Transferable[]
): Promise<T | null> {
  return new Promise<T | null>((resolve) => {
    const id = ++msgId;
    pending.set(id, { resolve: (msg) => resolve(msg as T | null) });
    try {
      worker.postMessage({ ...message, id }, transfer ?? []);
    } catch {
      pending.delete(id);
      resolve(null);
      return;
    }
    window.setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id);
        resolve(null);
      }
    }, timeoutMs);
  });
}
