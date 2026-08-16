import React from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Scale, ShieldCheck, XCircle, CheckCircle,
  TrendingUp, Percent, RefreshCw, Archive, AlertTriangle, BarChart2
} from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.06 } } };

const BANKROLL_LIMITS = [
  { label: 'Starting Bankroll', value: 'R1,000 ZAR', note: 'Virtual / fake money', color: 'emerald' },
  { label: 'Max Stake per Bet', value: '5%', note: 'Of current bankroll', color: 'purple' },
  { label: 'Daily Loss Limit', value: '20%', note: 'Auto-stops selections', color: 'amber' },
  { label: 'Kelly Fraction', value: '0.5 (Half)', note: 'Conservative staking', color: 'cyan' },
  { label: 'Min Edge Threshold', value: '≥ 5%', note: 'Required to select', color: 'blue' },
];

const SELECTION_CRITERIA = [
  { label: 'Edge ≥ 5%', desc: 'Model probability exceeds implied market probability by ≥ 5%' },
  { label: 'Data Quality ≥ Medium', desc: 'Sufficient form/odds data available' },
  { label: 'Race Verified', desc: 'Race exists on official card (TAB4Racing)' },
  { label: 'Odds Available', desc: 'Live odds from Betway/TAB' },
  { label: 'Bankroll Healthy', desc: 'Not in daily loss limit cooldown' },
];

const PROHIBITED = [
  'Overriding max bet (5%)',
  'Ignoring daily loss limit (20%)',
  'Betting without verified edge',
  'Manual stake adjustments outside Kelly',
  'Simulating multiple accounts to circumvent limits',
];

const PERFORMANCE_METRICS = [
  'Track, distance, surface, going',
  'Odds at placement vs. SP',
  'Edge % at placement',
  'Result (WON/LOST/VOID)',
  'P&L impact',
  'ROI by track / distance / odds band',
  'Strike rate by confidence tier',
  'Monthly P&L chart',
];

export const BettingRulesPage: React.FC = () => {
  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      variants={stagger}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent p-6 md:p-8">
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 text-white/60 hover:text-emerald-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
                  <Scale className="w-5 h-5 text-emerald-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">Betting Rules</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                These rules govern the <span className="text-emerald-400 font-bold">paper-trading simulation</span> within Strike Tips Racing Bot. They exist to teach disciplined bankroll management and racing analysis — not to facilitate real betting.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Effective: June 2026</span>
                <span className="text-[10px] px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full font-bold uppercase tracking-widest text-emerald-400">Version 1.0</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Critical notice */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="flex items-start gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <p className="text-sm font-bold text-rose-300 leading-relaxed">
            These limits <span className="text-rose-400">cannot be bypassed in the simulation</span>. The bankroll governor enforces all rules automatically.
          </p>
        </div>
      </motion.div>

      {/* Bankroll Limits */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          Bankroll Hard Limits
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {BANKROLL_LIMITS.map((limit, i) => (
            <motion.div
              key={i}
              variants={fadeUp}
              className={`p-4 rounded-xl border transition-all hover:scale-[1.02] ${
                limit.color === 'emerald' ? 'bg-emerald-500/5 border-emerald-500/20' :
                limit.color === 'purple' ? 'bg-purple-500/5 border-purple-500/20' :
                limit.color === 'amber' ? 'bg-amber-500/5 border-amber-500/20' :
                limit.color === 'cyan' ? 'bg-cyan-500/5 border-cyan-500/20' :
                'bg-blue-500/5 border-blue-500/20'
              }`}
            >
              <div className={`text-2xl font-black mb-1 ${
                limit.color === 'emerald' ? 'text-emerald-400' :
                limit.color === 'purple' ? 'text-purple-400' :
                limit.color === 'amber' ? 'text-amber-400' :
                limit.color === 'cyan' ? 'text-cyan-400' :
                'text-blue-400'
              }`}>{limit.value}</div>
              <div className="text-xs font-bold text-white mb-0.5">{limit.label}</div>
              <div className="text-[10px] text-white/50">{limit.note}</div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Selection Criteria */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          Selection Criteria
        </h2>
        <p className="text-xs text-white/50 mb-4">A paper trade is only recorded when ALL conditions are met:</p>
        <div className="space-y-2">
          {SELECTION_CRITERIA.map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] hover:border-emerald-500/20 transition-all">
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold text-white">{item.label}</div>
                <div className="text-xs text-white/55 mt-0.5">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Stake Calculation */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Percent className="w-5 h-5 text-purple-400" />
          Stake Calculation
        </h2>
        <div className="space-y-3">
          <div className="p-4 rounded-xl bg-black/40 border border-white/10 font-mono text-sm">
            <div className="text-[10px] text-white/40 uppercase tracking-widest mb-3 font-sans font-bold">Formula</div>
            <div className="space-y-1.5">
              <div className="text-cyan-400">Raw_Stake = (Model_Probability × Decimal_Odds − 1) × Kelly_Fraction × Edge</div>
              <div className="text-purple-400">Final_Stake = min(Raw_Stake, Current_Bankroll × 0.05)</div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
            <div className="text-[10px] text-emerald-400/60 uppercase tracking-widest font-bold mb-2">Example</div>
            <div className="font-mono text-xs space-y-1 text-white/70">
              <div>Bankroll: R1,200 | Edge: 8% | Odds: 4.0</div>
              <div className="text-emerald-400">Raw = 1,200 × 0.5 × 0.08 = R48</div>
              <div className="text-emerald-400">Cap = 1,200 × 0.05 = R60</div>
              <div className="text-white font-bold">Final = R48</div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Race Settlement */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <RefreshCw className="w-5 h-5 text-cyan-400" />
          Race Settlement
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'Auto-settlement', value: 'ResultTracker runs post-race via DuckDuckGo search + official pages' },
            { label: 'Matching', value: 'Fuzzy match horse name to winner' },
            { label: 'Outcomes', value: 'WON / LOST / VOID (non-runner)' },
            { label: 'VOID Cases', value: 'Horse scratched, race abandoned, result unavailable → stake returned' },
          ].map((item, i) => (
            <div key={i} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.08]">
              <div className="text-[10px] font-black text-cyan-400/60 uppercase tracking-widest mb-1">{item.label}</div>
              <div className="text-sm text-white/80">{item.value}</div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Prohibited */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <XCircle className="w-5 h-5 text-rose-400" />
          Prohibited in Simulation
        </h2>
        <div className="space-y-2">
          {PROHIBITED.map((item, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-rose-500/5 border border-rose-500/15">
              <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span className="text-sm text-white/80">{item}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Performance Tracking */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <BarChart2 className="w-5 h-5 text-blue-400" />
          Performance Tracking
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PERFORMANCE_METRICS.map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-white/65 p-2">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
              {item}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Reset & Archive */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Archive className="w-5 h-5 text-amber-400" />
          Reset & Archive
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { label: 'Manual Reset', value: 'Settings → "Reset Bankroll" (sets to R1,000, archives history)' },
            { label: 'Auto-archive', value: 'Monthly snapshot saved to ChromaDB' },
            { label: 'Export', value: '/api/betting/history returns full CSV-compatible JSON' },
          ].map((item, i) => (
            <div key={i} className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
              <div className="text-[10px] font-black text-amber-400/60 uppercase tracking-widest mb-1">{item.label}</div>
              <div className="text-xs text-white/70 leading-relaxed">{item.value}</div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Educational Intent + Disclaimer */}
      <motion.div variants={fadeUp}>
        <div className="p-5 rounded-xl bg-white/3 border border-white/10">
          <h2 className="text-sm font-black text-white/80 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            Educational Intent
          </h2>
          <p className="text-xs text-white/55 leading-relaxed mb-3">
            These rules mirror professional bankroll management. The simulation teaches discipline (hard limits), value identification (edge threshold), risk sizing (Kelly), and record-keeping (full audit trail).
          </p>
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <p className="text-xs font-bold text-amber-300">
              This is a paper-trading simulation only. No real money is wagered, won, or lost. Rules are for educational demonstration only.
            </p>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
