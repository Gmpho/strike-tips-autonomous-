// Operations timeline: stable event build + cross-linking (bets ↔ alerts
// ↔ healing). Pure functions — no React, fully testable. L7 rules:
// stable IDs (never Math.random — that remounted every row on every poll),
// linking by normalized identity from RAW objects (never message parsing),
// capped rendering downstream.

export interface OpsEvent {
  id: string;
  timestamp: string;
  category: 'BET' | 'ALERT' | 'SYSTEM';
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
  source: string;
  action: string;
  message: string;
  links: { kind: 'bet' | 'alert' | 'healing'; id: string; label: string }[];
}

export function normName(v: unknown): string {
  return String(v || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

interface RawAlert {
  type?: string;
  horse?: string;
  course?: string;
  odds?: string | number;
  timestamp?: string;
  race?: string | number;
}

interface RawBet {
  id?: string;
  horse?: string;
  track?: string;
  raceNumber?: string | number;
  stake?: number;
  odds?: number;
  edgePercent?: number;
  placedAt?: string;
  settled?: boolean;
  won?: boolean | null;
  payout?: number | null;
}

interface RawHealing {
  id?: string;
  timestamp?: string;
  agent?: string;
  action?: string;
  details?: string;
  status?: string;
}

const BET_ID_RE = /\b(20\d{6}[A-Z0-9_-]+)\b/;
const keyOf = (horse: unknown, track: unknown) =>
  `${normName(horse)}|${normName(track)}`;

export function buildTimeline(input: {
  healing?: RawHealing[] | null;
  alerts?: RawAlert[] | null;
  bets?: RawBet[] | null;
}): OpsEvent[] {
  const list: OpsEvent[] = [];
  const betIndex = new Map<string, OpsEvent[]>();
  const alertIndex = new Map<string, OpsEvent[]>();

  const linkBetAlert = (betEv: OpsEvent, alertEv: OpsEvent) => {
    if (!betEv.links.some((l) => l.id === alertEv.id)) {
      betEv.links.push({ kind: 'alert', id: alertEv.id, label: alertEv.action });
    }
    if (!alertEv.links.some((l) => l.id === betEv.id)) {
      alertEv.links.push({ kind: 'bet', id: betEv.id, label: betEv.action });
    }
  };

  (input.healing || []).forEach((e, i) => {
    const status = String(e.status || '').toUpperCase();
    list.push({
      id: `sys-${e.timestamp || 'na'}-${i}`,
      timestamp: e.timestamp || '',
      category: 'SYSTEM',
      level: status === 'FAILURE' ? 'ERROR' : status === 'SUCCESS' ? 'SUCCESS' : 'INFO',
      source: e.agent || 'System',
      action: e.action || 'EVENT',
      message: e.details || '',
      links: [],
    });
  });

  (input.alerts || []).forEach((a, idx) => {
    const typeLabel = a.type === 'odds_drop' ? 'Odds Drop' : a.type === 'value_bet' ? 'Value Bet' : a.type;
    const race = a.race !== undefined && a.race !== null && String(a.race) !== '' ? ` R${a.race}` : '';
    const ev: OpsEvent = {
      id: `alert-${a.timestamp || 'na'}-${idx}`,
      timestamp: a.timestamp || '',
      category: 'ALERT',
      level: a.type === 'odds_drop' ? 'WARN' : 'INFO',
      source: 'AlertEngine',
      action: String(a.type || 'ALERT').toUpperCase(),
      message: `${a.horse} @ ${a.course}${race}: Opportunity detected (${typeLabel} | Odds: ${a.odds})`,
      links: [],
    };
    list.push(ev);
    const k = keyOf(a.horse, a.course);
    if (k !== '|') {
      const arr = alertIndex.get(k) || [];
      arr.push(ev);
      alertIndex.set(k, arr);
      for (const b of betIndex.get(k) || []) linkBetAlert(b, ev);
    }
  });

  (input.bets || []).forEach((b) => {
    const ts = b.placedAt || new Date().toISOString();
    const stake = Number(b.stake ?? 0).toFixed(2);
    const mk = (id: string, settled: boolean, won: boolean): OpsEvent => ({
      id,
      timestamp: ts,
      category: 'BET',
      level: settled ? (won ? 'SUCCESS' : 'WARN') : 'INFO',
      source: 'Governor',
      action: !settled ? 'PLACE_BET' : won ? 'BET_WON' : 'BET_LOST',
      message: !settled
        ? `Placed R${stake} on ${b.horse} @ ${b.track} R${b.raceNumber} (Odds: ${b.odds}, Edge: +${b.edgePercent}%)`
        : `Settled bet on ${b.horse} @ ${b.track} R${b.raceNumber}: ${won ? `WON (+R${Number(b.payout ?? 0).toFixed(2)})` : 'LOST'}`,
      links: [],
    });
    const placeEv = mk(`bet-place-${b.id || `${b.horse}-${ts}`}`, false, false);
    list.push(placeEv);
    const k = keyOf(b.horse, b.track);
    if (k !== '|') {
      const arr = betIndex.get(k) || [];
      arr.push(placeEv);
      betIndex.set(k, arr);
      for (const a of alertIndex.get(k) || []) linkBetAlert(placeEv, a);
    }
    if (b.settled) {
      const won = b.won === true;
      const settleEv = mk(`bet-settle-${b.id || `${b.horse}-${ts}`}`, true, won);
      list.push(settleEv);
      if (k !== '|') {
        betIndex.get(k)?.push(settleEv);
        for (const a of alertIndex.get(k) || []) linkBetAlert(settleEv, a);
      }
    }
  });

  // Healing → bet via bet_id in details (voids, resettles, awaiting-dividend).
  for (const e of list) {
    if (e.category !== 'SYSTEM') continue;
    const m = BET_ID_RE.exec(e.message);
    if (!m) continue;
    const target = list.find(
      (o) => o.category === 'BET' && o.id.endsWith(m[1]),
    );
    if (target && !e.links.some((l) => l.id === target.id)) {
      e.links.push({ kind: 'bet', id: target.id, label: 'BET' });
      if (!target.links.some((l) => l.id === e.id)) {
        target.links.push({ kind: 'healing', id: e.id, label: e.action });
      }
    }
  }

  return list.sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
}
