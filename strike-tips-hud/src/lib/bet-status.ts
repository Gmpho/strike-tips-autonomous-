import type { BetRecord } from '../types';

/**
 * The ledger's single source of truth for a bet's state (Oct-2026).
 *
 * Terminally voided tickets (VOID/EXPIRED) carry `settled=false` but are NOT
 * open money — the stake has already been returned. Deriving the label from
 * `settled`/`won` alone therefore shows every VOID ticket as "OPEN" forever
 * (110 exotic tickets in the Oct-2026 ledger). Always derive through here.
 */
export type BetStatus = 'WON' | 'LOST' | 'PENDING' | 'VOID' | 'EXPIRED';

export function betStatus(bet: BetRecord): BetStatus {
  const s = String(bet.status || '').toUpperCase();
  if (s === 'WON' || s === 'LOST' || s === 'VOID' || s === 'EXPIRED' || s === 'PENDING') return s;
  if (bet.settled) return bet.won ? 'WON' : 'LOST';
  return 'PENDING';
}

/** True when the stake came back: not won, not lost, not still open. */
export function isRefunded(bet: BetRecord): boolean {
  const st = betStatus(bet);
  return st === 'VOID' || st === 'EXPIRED';
}

/** Realised P&L, or null while the ticket is still open. */
export function betPnl(bet: BetRecord): number | null {
  const st = betStatus(bet);
  const stake = bet.stake ?? 0;
  if (st === 'WON') return (bet.payout ?? 0) - stake;
  if (st === 'LOST') return -stake;
  if (st === 'VOID' || st === 'EXPIRED') return 0;
  return null;
}
