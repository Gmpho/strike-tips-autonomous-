import { useState, useEffect, useCallback } from 'react';

const UPDATE_POLL_MS = 60_000;

export function usePWA() {
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isInstallable, setIsInstallable] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [hasUpdate, setHasUpdate] = useState(false);
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches
      || (navigator as any).standalone
      || document.referrer.includes('android-app://');

    setIsInstalled(isStandalone);

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setIsInstallable(true);
    };

    const handleAppInstalled = () => {
      setDeferredPrompt(null);
      setIsInstallable(false);
      setIsInstalled(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    let updateTimer: number | undefined;
    let cancelled = false;
    const onVisibility = () => {
      navigator.serviceWorker.getRegistration('/sw.js').then((reg) => {
        if (reg && !document.hidden) reg.update().catch(() => { /* noop */ });
      }).catch(() => { /* noop */ });
    };

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).then((reg) => {
        if (cancelled) return;

        // If a newer worker is already installed and waiting, surface the toast
        if (reg.waiting) {
          setHasUpdate(true);
          setWaitingWorker(reg.waiting);
        }

        // Detect newly-installing workers
        reg.onupdatefound = () => {
          const installing = reg.installing;
          if (!installing) return;
          installing.onstatechange = () => {
            if (installing.state === 'installed' && navigator.serviceWorker.controller) {
              setHasUpdate(true);
              setWaitingWorker(installing);
            }
          };
        };

        // Actively ping the update check while the tab stays open:
        // browsers only re-fetch sw.js on navigation, so a long-lived tab
        // would otherwise never learn about a new deployment.
        const poll = () => {
          if (!cancelled) reg.update().catch(() => { /* offline / browser cadence */ });
        };
        poll();
        updateTimer = window.setInterval(poll, UPDATE_POLL_MS);

        // Re-check immediately when the tab regains focus
        document.addEventListener('visibilitychange', onVisibility);
        window.addEventListener('focus', onVisibility);
      });
    }

    return () => {
      cancelled = true;
      if (updateTimer !== undefined) clearInterval(updateTimer);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('focus', onVisibility);
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const installPWA = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome: _outcome } = await deferredPrompt.userChoice;
    setDeferredPrompt(null);
    setIsInstallable(false);
  };

  const updateSW = useCallback(() => {
    if (waitingWorker) {
      waitingWorker.postMessage({ type: 'SKIP_WAITING' });
    }
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload();
    });
  }, [waitingWorker]);

  return {
    isInstallable,
    isInstalled,
    installPWA,
    hasUpdate,
    updateSW,
  };
}