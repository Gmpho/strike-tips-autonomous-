export const MODEL_MAPPING: Record<string, string> = {
  "webllm-qwen-0.5b": "Qwen2.5-0.5B-Instruct-q4f16_1-MLC",
  "webllm-llama-1b": "Llama-3.2-1B-Instruct-q4f16_1-MLC",
  "webllm-qwen-1.5b": "Qwen2.5-1.5B-Instruct-q4f16_1-MLC",
};

let engineInstance: any = null;
let currentModelId = "";

export interface LoadProgress {
  progress: number;
  text: string;
}

/**
 * Checks if WebGPU is supported in the current browser/device context.
 */
export async function checkWebGPUSupport(): Promise<boolean> {
  if (typeof navigator === "undefined") {
    return false;
  }
  const nav = navigator as any;
  if (!nav.gpu) {
    return false;
  }
  try {
    const adapter = await nav.gpu.requestAdapter();
    return !!adapter;
  } catch {
    return false;
  }
}

export interface StorageEstimateInfo {
  quota: number;
  usage: number;
  free: number;
  percentage: number;
  isSupported: boolean;
}

/**
 * Checks the browser's remaining storage quota.
 */
export async function getStorageEstimate(): Promise<StorageEstimateInfo> {
  if (typeof navigator === "undefined" || !navigator.storage || !navigator.storage.estimate) {
    return { quota: 0, usage: 0, free: 0, percentage: 0, isSupported: false };
  }
  try {
    const est = await navigator.storage.estimate();
    const quota = est.quota || 0;
    const usage = est.usage || 0;
    const free = Math.max(0, quota - usage);
    const percentage = quota > 0 ? Math.round((usage / quota) * 100) : 0;
    return { quota, usage, free, percentage, isSupported: true };
  } catch (e) {
    console.error("[WebLLM Storage Estimate Error]", e);
    return { quota: 0, usage: 0, free: 0, percentage: 0, isSupported: false };
  }
}

/**
 * Recursively deletes OPFS directory entries, clears WebLLM Cache entries, and cleans up engine states.
 */
export async function clearWebLLMStorage(): Promise<boolean> {
  let clearedOPFS = false;
  let clearedCache = false;

  // 1. Clear OPFS recursively
  if (typeof navigator !== "undefined" && navigator.storage && (navigator.storage as any).getDirectory) {
    try {
      const root = await (navigator.storage as any).getDirectory();
      if (root && typeof root.values === 'function') {
        for await (const entry of (root as any).values()) {
          try {
            await root.removeEntry(entry.name, { recursive: true });
          } catch (err) {
            console.warn(`[WebLLM Storage] Failed to remove entry ${entry.name}:`, err);
          }
        }
      }
      clearedOPFS = true;
      console.log("[WebLLM Storage] OPFS storage cleared successfully!");
    } catch (e) {
      console.error("[WebLLM Storage] Failed to clear OPFS:", e);
    }
  }

  // 2. Delete webllm cache entries if they exist
  if (typeof window !== "undefined" && window.caches) {
    try {
      const cacheNames = await window.caches.keys();
      for (const name of cacheNames) {
        if (name.includes("webllm") || name.includes("mlc")) {
          await window.caches.delete(name);
          clearedCache = true;
        }
      }
      console.log("[WebLLM Storage] Cache Storage cleared successfully!");
    } catch (e) {
      console.error("[WebLLM Storage] Failed to clear Cache Storage:", e);
    }
  }

  // 3. Clear IndexedDB webllm databases
  if (typeof window !== "undefined" && window.indexedDB) {
    try {
      const databases = (window.indexedDB as any).databases;
      if (databases) {
        const dbs = await databases();
        for (const db of dbs) {
          if (db.name && (db.name.includes("webllm") || db.name.includes("mlc"))) {
            window.indexedDB.deleteDatabase(db.name);
          }
        }
      }
    } catch (e) {
      console.warn("[WebLLM Storage] Failed to clear IndexedDB databases:", e);
    }
  }

  // Force reset global state
  if (engineInstance) {
    try {
      await engineInstance.unload();
    } catch {}
    engineInstance = null;
    currentModelId = "";
  }

  return clearedOPFS || clearedCache;
}

/**
 * Initializes and retrieves the WebLLM engine singleton instance.
 */
export async function getWebLLMEngine(
  alias: string,
  onProgress?: (p: LoadProgress) => void
): Promise<any> {
  const modelId = MODEL_MAPPING[alias];
  if (!modelId) {
    throw new Error(`Unknown WebLLM model alias: ${alias}`);
  }

  // Request storage persistence programmatically to avoid browser evicting the weights
  if (typeof navigator !== "undefined" && navigator.storage && navigator.storage.persist) {
    try {
      const isPersisted = await navigator.storage.persist();
      console.log(`[WebLLM Storage] Storage persistence granted: ${isPersisted}`);
    } catch (e) {
      console.warn("[WebLLM Storage] Requesting storage persistence failed:", e);
    }
  }

  if (engineInstance && currentModelId === modelId) {
    console.log("[WebLLM] Reusing already loaded engine instance for:", modelId);
    return engineInstance;
  }

  if (engineInstance) {
    console.log("[WebLLM] Unloading previous model:", currentModelId);
    try {
      await engineInstance.unload();
    } catch {}
    engineInstance = null;
  }

  console.log("[WebLLM] Initializing model:", modelId);
  currentModelId = modelId;

  // Dynamic import to prevent initial bundle bloat (reduces bundle size by 6MB)
  const { CreateWebWorkerMLCEngine, prebuiltAppConfig } = await import("@mlc-ai/web-llm");

  const allowedModelIds = Object.values(MODEL_MAPPING);
  const filteredModelList = prebuiltAppConfig.model_list.filter((m) =>
    allowedModelIds.includes(m.model_id)
  );

  // Initialize the worker in the background URL
  const worker = new Worker(
    new URL("../workers/webllm.worker.ts", import.meta.url),
    { type: "module" }
  );

  engineInstance = await CreateWebWorkerMLCEngine(
    worker,
    modelId,
    {
      appConfig: {
        ...prebuiltAppConfig,
        model_list: filteredModelList,
        cacheBackend: "opfs",
      },
      initProgressCallback: (report: any) => {
        console.log(`[WebLLM Progress] ${report.text} (${Math.round(report.progress * 100)}%)`);
        if (onProgress) {
          onProgress({
            progress: report.progress,
            text: report.text,
          });
        }
      },
    }
  );

  // Defensively force explicit reload to ensure model is 100% active in WebWorker
  console.log("[WebLLM] Verifying engine model activation...");
  await engineInstance.reload(modelId);

  return engineInstance as any;
}

/**
 * Resets the WebLLM engine singleton instance state.
 */
export function resetWebLLMEngine(): void {
  if (engineInstance) {
    try {
      engineInstance.unload();
    } catch {}
    engineInstance = null;
  }
  currentModelId = "";
  console.log("[WebLLM] Engine singleton state reset completed.");
}
