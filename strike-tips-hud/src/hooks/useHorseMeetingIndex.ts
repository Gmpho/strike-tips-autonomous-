import { useMemo } from 'react';
import type { RaceEvent, Runner } from '../types';

export interface MeetingRef {
  runner: Runner;
  course: string;
  time: string;
}

/** Horse name → live-market runner + its meeting (course/time).
 *  Shared by Predictor and Market Movers so ATR cards always show WHERE. */
export function buildMeetingIndex(
  events: Record<string, RaceEvent>,
): Map<string, MeetingRef> {
  const index = new Map<string, MeetingRef>();
  Object.values(events || {}).forEach((event: RaceEvent) => {
    (event.runners || []).forEach((r) => {
      const key = ((r.outcomeName || r.name) || '').trim().toLowerCase();
      if (key && !index.has(key)) {
        index.set(key, { runner: r, course: event.course || '', time: event.t || '' });
      }
    });
  });
  return index;
}

export function useHorseMeetingIndex(
  events: Record<string, RaceEvent>,
): Map<string, MeetingRef> {
  return useMemo(() => buildMeetingIndex(events), [events]);
}
