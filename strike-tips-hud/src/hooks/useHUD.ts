import { useEffect, useSyncExternalStore } from 'react';
import { hudStore } from '../store/hud-store';
import { dataBridge } from '../engine/data-bridge';
import type { HUDState } from '../types';

/**
 * useHUD — Single source of truth for dashboard state.
 * 
 * The DataBridge handles all API polling (5s interval) and writes
 * to hudStore. This hook subscribes to hudStore so React components
 * re-render when new data arrives. No duplicate fetching.
 */
export function useHUD(): HUDState {
  // Start the DataBridge on first mount (idempotent)
  useEffect(() => {
    dataBridge.start();
    return () => dataBridge.stop();
  }, []);

  // Subscribe to store updates — React re-renders when hudStore.notify() fires
  const state = useSyncExternalStore(
    (callback) => hudStore.subscribe(callback),
    () => hudStore.getState()
  );

  return state;
}

