import React from 'react';
import { TrendingUp, TrendingDown, Minus, Eye, MapPin, Clock, BarChart2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import type { MarketMover } from '../../types';

import { getFullCourseName } from '../../lib/course-names';

// ─── Robust Movement Direction Parser ────────────────────────────────────────
interface MovementInfo {
  direction: 'shortened' | 'drifted' | 'stable';
  label: string;
  numericChange: number | null;
}

function parseMovement(movement: string): MovementInfo {
  if (!movement || movement.trim() === '' || movement === '—') {
    return { direction: 'stable', label: 'Stable', numericChange: null };
  }

  const raw = movement.trim();
  const m = raw.toLowerCase();

  // 1) Explicit keyword detection
  if (
    m.includes('shorten') || m.includes('backed') || m.includes('firmed') ||
    m.includes('in') || m.includes('down') || m.startsWith('-')
  ) {
    const num = extractNumeric(raw);
    return { direction: 'shortened', label: raw, numericChange: num ? -Math.abs(num) : null };
  }
  if (
    m.includes('drift') || m.includes('out') || m.includes('up') ||
    m.includes('eased') || m.startsWith('+')
  ) {
    const num = extractNumeric(raw);
    return { direction: 'drifted', label: raw, numericChange: num ? Math.abs(num) : null };
  }

  // 2) Arrow pattern e.g. "5.00 → 3.50" or "3.50 > 5.00"
  const arrowMatch = raw.match(/(\d+\.?\d*)\s*(?:→|->|>|to)\s*(\d+\.?\d*)/i);
  if (arrowMatch) {
    const from = parseFloat(arrowMatch[1]);
    const to   = parseFloat(arrowMatch[2]);
    if (to < from) {
      return { direction: 'shortened', label: raw, numericChange: -(((from - to) / from) * 100) };
    }
    if (to > from) {
      return { direction: 'drifted', label: raw, numericChange: ((to - from) / from) * 100 };
    }
    return { direction: 'stable', label: raw, numericChange: 0 };
  }

  // 3) Plain numeric with optional sign
  const numMatch = raw.match(/^([+-]?\d+\.?\d*)%?$/);
  if (numMatch) {
    const val = parseFloat(numMatch[1]);
    if (val < 0) return { direction: 'shortened', label: `${Math.abs(val)}% Shorter`, numericChange: val };
    if (val > 0) return { direction: 'drifted', label: `${val}% Drifted`, numericChange: val };
    return { direction: 'stable', label: 'Stable', numericChange: 0 };
  }

  // 4) Percentage anywhere in string
  const pctMatch = raw.match(/([+-]?\d+\.?\d*)%/);
  if (pctMatch) {
    const val = parseFloat(pctMatch[1]);
    if (val < 0) return { direction: 'shortened', label: raw, numericChange: val };
    if (val > 0) return { direction: 'drifted', label: raw, numericChange: val };
    return { direction: 'stable', label: raw, numericChange: 0 };
  }

  // 5) Fallback — return as-is with stable
  return { direction: 'stable', label: raw, numericChange: null };
}

function extractNumeric(s: string): number | null {
  const m = s.match(/(\d+\.?\d*)/);
  return m ? parseFloat(m[1]) : null;
}

// ─── Movement Badge Component ─────────────────────────────────────────────────
function MovementBadge({ movement }: { movement: string }) {
  const info = parseMovement(movement);

  if (info.direction === 'shortened') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-black text-xs tabular-nums">
        <TrendingDown className="w-3.5 h-3.5 shrink-0" />
        <span>{info.label}</span>
      </span>
    );
  }

  if (info.direction === 'drifted') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 font-black text-xs tabular-nums">
        <TrendingUp className="w-3.5 h-3.5 shrink-0" />
        <span>{info.label}</span>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-500/10 border border-slate-500/20 text-slate-400 font-bold text-xs">
      <Minus className="w-3.5 h-3.5 shrink-0" />
      <span>{info.label || 'Stable'}</span>
    </span>
  );
}

// ─── Direction colour for the odds change ────────────────────────────────────
function oddsChangeColor(movement: string): string {
  const { direction } = parseMovement(movement);
  if (direction === 'shortened') return 'text-emerald-400';
  if (direction === 'drifted')   return 'text-red-400';
  return 'text-slate-400';
}

// ─── Single Mover Card ────────────────────────────────────────────────────────
function MoverCard({ mover, index }: { mover: MarketMover; index: number }) {
  const fullCourse = getFullCourseName(mover.course);
  const { direction } = parseMovement(mover.movement);

  const accentBorder =
    direction === 'shortened' ? 'border-l-emerald-500/60' :
    direction === 'drifted'   ? 'border-l-red-500/60'     :
    'border-l-slate-500/30';

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className={`rounded-2xl bg-theme-panel border border-theme border-l-4 ${accentBorder} sidebar-card p-4 hover:bg-white/5 transition-all duration-200 hover:border-white/20`}
    >
      {/* Horse Name + Movement Badge */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="text-sm font-black text-theme-primary tracking-tight leading-snug truncate">
            {mover.horse}
          </h3>
          <p className="text-[10px] font-bold text-theme-secondary uppercase tracking-wider mt-0.5 flex items-center gap-1">
            <Clock className="w-2.5 h-2.5 shrink-0" />
            {mover.time}
          </p>
        </div>
        <MovementBadge movement={mover.movement} />
      </div>

      {/* Venue */}
      <div className="flex items-start gap-1.5 mb-3">
        <MapPin className="w-3 h-3 text-theme-secondary shrink-0 mt-0.5" />
        <p className="text-[11px] font-semibold text-theme-secondary leading-snug">
          {fullCourse}
        </p>
      </div>

      {/* Odds Row */}
      <div className="flex items-center gap-3 bg-black/20 rounded-xl px-3 py-2 border border-white/5">
        <div className="flex-1">
          <p className="text-[9px] font-black text-theme-secondary uppercase tracking-widest mb-0.5">
            Opening
          </p>
          <p className="text-sm font-black text-slate-400 tabular-nums">
            {mover.first_show || '—'}
          </p>
        </div>

        <div className="text-slate-600 text-lg font-light select-none">→</div>

        <div className="flex-1 text-right">
          <p className="text-[9px] font-black text-theme-secondary uppercase tracking-widest mb-0.5">
            Current
          </p>
          <p className={`text-sm font-black tabular-nums ${oddsChangeColor(mover.movement)}`}>
            {mover.current_odds || '—'}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Legend Strip ─────────────────────────────────────────────────────────────
function MarketLegend() {
  return (
    <div className="flex items-center gap-4 text-[9px] font-black uppercase tracking-widest">
      <span className="flex items-center gap-1.5 text-emerald-400">
        <TrendingDown className="w-3 h-3" />
        Shortened (Backed)
      </span>
      <span className="flex items-center gap-1.5 text-red-400">
        <TrendingUp className="w-3 h-3" />
        Drifted (Eased)
      </span>
    </div>
  );
}

// ─── Main View ────────────────────────────────────────────────────────────────
export const MarketMoversView: React.FC = () => {
  const store = useHUD();
  const marketMovers = Array.isArray(store.marketMovers) ? store.marketMovers : [];

  const shortened = marketMovers.filter(m => parseMovement(m.movement).direction === 'shortened');
  const drifted   = marketMovers.filter(m => parseMovement(m.movement).direction === 'drifted');
  const stable    = marketMovers.filter(m => parseMovement(m.movement).direction === 'stable');

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-6 h-full flex flex-col"
    >
      {/* ── Header ── */}
      <div className="shrink-0 space-y-3">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent">
            Market Movers
          </h2>
          <p className="text-xs text-theme-secondary mt-1 font-semibold">
            Live odds movements — horses attracting significant market activity
          </p>
        </div>

        {/* Summary stats */}
        {marketMovers.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
              <p className="text-lg font-black text-emerald-400">{shortened.length}</p>
              <p className="text-[9px] font-black text-emerald-500/70 uppercase tracking-widest">Shortened</p>
            </div>
            <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-center">
              <p className="text-lg font-black text-red-400">{drifted.length}</p>
              <p className="text-[9px] font-black text-red-500/70 uppercase tracking-widest">Drifted</p>
            </div>
            <div className="p-2.5 rounded-xl bg-white/5 border border-white/10 text-center">
              <p className="text-lg font-black text-slate-400">{stable.length}</p>
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Stable</p>
            </div>
          </div>
        )}

        <MarketLegend />
      </div>

      {/* ── Content ── */}
      {marketMovers.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-theme-secondary">
          <div className="p-6 rounded-3xl bg-white/5 border border-white/10 flex flex-col items-center gap-4">
            <Eye className="w-10 h-10 opacity-30" />
            <div className="text-center space-y-1">
              <p className="text-sm font-bold text-theme-primary/60">No Market Movers Detected</p>
              <p className="text-xs text-theme-secondary">
                Monitoring live odds — data refreshes every 30 seconds
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar scroll-container pr-1 -mr-1 space-y-6">

          {/* Shortened / Backed */}
          {shortened.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />
                <h3 className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">
                  Backed — Odds Shortened
                </h3>
                <div className="flex-1 h-px bg-emerald-500/20" />
                <span className="text-[9px] font-black text-emerald-500/60 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                  {shortened.length}
                </span>
              </div>
              <div className="space-y-2.5">
                {shortened.map((mover, i) => (
                  <MoverCard key={`${mover.horse}-${mover.course}-${i}`} mover={mover} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* Drifted */}
          {drifted.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-red-400" />
                <h3 className="text-[10px] font-black text-red-400 uppercase tracking-widest">
                  Drifted — Odds Lengthened
                </h3>
                <div className="flex-1 h-px bg-red-500/20" />
                <span className="text-[9px] font-black text-red-500/60 bg-red-500/10 px-2 py-0.5 rounded-full">
                  {drifted.length}
                </span>
              </div>
              <div className="space-y-2.5">
                {drifted.map((mover, i) => (
                  <MoverCard key={`${mover.horse}-${mover.course}-${i}`} mover={mover} index={shortened.length + i} />
                ))}
              </div>
            </div>
          )}

          {/* Stable */}
          {stable.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <BarChart2 className="w-3.5 h-3.5 text-slate-500" />
                <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
                  Stable — No Significant Move
                </h3>
                <div className="flex-1 h-px bg-slate-500/20" />
                <span className="text-[9px] font-black text-slate-500/60 bg-slate-500/10 px-2 py-0.5 rounded-full">
                  {stable.length}
                </span>
              </div>
              <div className="space-y-2.5">
                {stable.map((mover, i) => (
                  <MoverCard key={`${mover.horse}-${mover.course}-${i}`} mover={mover} index={shortened.length + drifted.length + i} />
                ))}
              </div>
            </div>
          )}

        </div>
      )}

      {/* Footer */}
      {marketMovers.length > 0 && (
        <div className="shrink-0 pt-3 border-t border-theme">
          <p className="text-[10px] text-theme-secondary font-semibold">
            {marketMovers.length} movers tracked — sourced live from ATR odds feed
          </p>
        </div>
      )}
    </motion.div>
  );
};
