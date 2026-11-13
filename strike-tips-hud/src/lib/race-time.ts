// Snapshot off-times are UTC wall-clocks, not local ones.
//
// The market snapshot stores HH:MM in UTC ("14:15" for Bahrain R1) while every
// reader treats it as a clock face. South Africa is UTC+2 with no daylight
// saving, so the correction is a fixed +2h — no tz database, no DST rules.
//
// Proof it is UTC and not local, 13 Nov 2026:
//   Fairview R1   snapshot 10:10  · Betfair epoch->SAST 12:10
//   Greyville R1  snapshot 14:37  · Betfair epoch->SAST 16:37
//   Bahrain R1    snapshot 14:15  · published SA start  16:15
//
// This converts for DISPLAY ONLY. Liveness and expiry compare the stored UTC
// value against a UTC clock and are already correct — do not feed them through
// here.
// Run: node --test tests/race-time.test.ts

/** South Africa is UTC+2 year-round (no DST). */
export const SAST_OFFSET_MINUTES = 120;

const HHMM = /^(\d{1,2}):(\d{2})$/;

/**
 * Convert a snapshot UTC wall-clock to the SA clock face.
 *
 * Anything unrecognised is returned untouched: a card showing "TBA" is honest,
 * a card inventing a time is not.
 */
export function offTimeLocal(t: string | null | undefined): string {
  if (!t) return '';
  const m = HHMM.exec(String(t).trim());
  if (!m) return String(t);

  const h = Number(m[1]);
  const min = Number(m[2]);
  if (!Number.isFinite(h) || !Number.isFinite(min) || h > 23 || min > 59) {
    return String(t);
  }

  const total = (h * 60 + min + SAST_OFFSET_MINUTES) % (24 * 60);
  const hh = String(Math.floor(total / 60)).padStart(2, '0');
  const mm = String(total % 60).padStart(2, '0');
  return `${hh}:${mm}`;
}
