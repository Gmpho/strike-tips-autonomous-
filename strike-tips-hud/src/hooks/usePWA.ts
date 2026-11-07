import { useCallback, useEffect, useSyncExternalStore } from 'react';

const UPDATE_POLL_MS = 60_000;

interface PWAState {
  isInstallable: boolean;
  isInstalled: boolean;
  hasUpdate: boolean;
  waitingWorker: ServiceWorker | null;
}

const initial: PWAState = {
  isInstallable: false,
  isInstalled: false,
  hasUpdate: false,
  waitingWorker: null,
};

// One shared store for the whole app.
//
// usePWA() used to keep its state in the calling component, and it was called
// three times (App.tsx x2 + usePromoActions), so we registered the service
// worker three times, ran three 60s update polls and had three independent
// `hasUpdate` flags — only one of which drove <UpdateToast>. The store makes
// registration and update detection happen exactly once.
let snapshot: PWAState = initial;
let started = false;
let deferredPrompt: any = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function setState(patch: Partial<PWAState>) {
  snapshot = { ...snapshot, ...patch };
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return snapshot;
}

function start() {
  if (started || typeof window === 'undefined') return;
  started = true;

  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as any).standalone ||
    document.referrer.includes('android-app://');

  setState({ isInstalled: isStandalone });

  window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault();
    deferredPrompt = e;
    setState({ isInstallable: true, isInstalled: false });
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    setState({ isInstallable: false, isInstalled: true });
  });

  if (!('serviceWorker' in navigator)) return;

  let cancelled = false;

  const checkForUpdate = () => {
    navigator.serviceWorker
      .getRegistration('/sw.js')
      .then((reg) => {
        if (reg && !document.hidden) reg.update().catch(() => { /* noop */ });
      })
      .catch(() => { /* noop */ });
  };

  navigator.serviceWorker
    .register('/sw.js', { updateViaCache: 'none' })
    .then((reg) => {
      if (cancelled) return;

      // A worker that is already installed and waiting means an update is
      // sitting there right now — surface the prompt immediately.
      if (reg.waiting) {
        setState({ hasUpdate: true, waitingWorker: reg.waiting });
      }

      reg.onupdatefound = () => {
        const installing = reg.installing;
        if (!installing) return;
        installing.onstatechange = () => {
          // `installed` + an existing controller == an update (not first run).
          if (installing.state === 'installed' && navigator.serviceWorker.controller) {
            setState({ hasUpdate: true, waitingWorker: installing });
          }
        };
      };

      // Browsers only re-fetch sw.js on navigation, so a long-lived tab would
      // never notice a deploy. Poll, and re-check the moment the tab refocuses.
      const poll = () => {
        if (!cancelled) reg.update().catch(() => { /* offline / cadence */ });
      };
      poll();
      window.setInterval(poll, UPDATE_POLL_MS);

      document.addEventListener('visibilitychange', checkForUpdate);
      window.addEventListener('focus', checkForUpdate);
    })
    .catch(() => { /* SW unsupported/blocked — app still works online */ });

  // A deploy that lands while the tab is backgrounded is picked up on return.
  document.addEventListener('visibilitychange', () => {
    if (!cancelled && !document.hidden) checkForUpdate();
  });

  // Reload as soon as the new worker takes control.
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    window.location.reload();
  });
}

const installPWA = async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  try {
    await deferredPrompt.userChoice;
  } finally {
    deferredPrompt = null;
    setState({ isInstallable: false });
  }
};

const updateSW = () => {
  // Activation is what fires `controllerchange` (which reloads the page).
  // If there is no waiting worker we are already on the newest build — a
  // plain reload is still the right answer, and it is what the old
  // implementation forgot to do.
  if (snapshot.waitingWorker) {
    snapshot.waitingWorker.postMessage({ type: 'SKIP_WAITING' });
    return;
  }
  window.location.reload();
};

export function usePWA() {
  // Registration is a side effect of *first use*, not of every consumer.
  useEffect(() => {
    start();
  }, []);

  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  const stableUpdate = useCallback(updateSW, []);
  const stableInstall = useCallback(installPWA, []);

  return {
    isInstallable: state.isInstallable,
    isInstalled: state.isInstalled,
    hasUpdate: state.hasUpdate,
    installPWA: stableInstall,
    updateSW: stableUpdate,
  };
}
