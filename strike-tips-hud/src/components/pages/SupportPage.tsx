import React from 'react';
import { motion } from 'framer-motion';
import { Coffee, Check, Minus, ArrowLeft } from 'lucide-react';
import { SUPPORT_TIERS, SUPPORT_COSTS_LINE, SUPPORT_TEST_MODE, TIER_PERKS } from '../../lib/support';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

export const SupportPage: React.FC = () => {
  return (
    <motion.div
      className="flex-1 flex flex-col min-h-0 pb-8"
      variants={{ animate: { transition: { staggerChildren: 0.06 } } }}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="relative overflow-hidden rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent p-6 md:p-8">
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-amber-500/10 text-theme-secondary hover:text-amber-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                  <Coffee className="w-5 h-5 text-amber-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-theme-primary">
                  Keep Strike Tips Running
                </h1>
              </div>
              <p className="text-sm text-theme-secondary font-medium max-w-2xl leading-relaxed">
                {SUPPORT_COSTS_LINE}
              </p>
              {SUPPORT_TEST_MODE && (
                <p className="inline-block text-[10px] font-black uppercase tracking-widest text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1 mt-3">
                  Test mode — no real money moves
                </p>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Tier cards */}
      <motion.div variants={fadeUp} className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-stretch mb-6">
        {SUPPORT_TIERS.map((t) => {
          const perks = TIER_PERKS[t.key] || { included: [], excluded: [] };
          const featured = t.key === 'champion';
          return (
            <div
              key={t.key}
              className={`relative rounded-3xl p-5 flex flex-col transition-all ${
                featured
                  ? 'bg-gradient-to-b from-purple-600/25 via-purple-900/30 to-theme-panel border border-purple-500/50 shadow-[0_0_40px_rgba(168,85,247,0.25)] sm:scale-[1.03] z-10'
                  : 'bg-theme-panel border border-theme'
              }`}
            >
              {t.saveBadge && (
                <span className="absolute -top-2.5 right-4 px-2 py-0.5 text-[9px] font-black rounded-full bg-purple-500 text-white uppercase tracking-wider shadow-lg">
                  {t.saveBadge}
                </span>
              )}
              <h2 className={`text-sm font-black uppercase tracking-tight ${featured ? 'text-white' : 'text-theme-primary'}`}>
                {t.name}
              </h2>
              <p className={`text-[11px] font-semibold mt-0.5 mb-3 min-h-[28px] ${featured ? 'text-white/70' : 'text-theme-secondary'}`}>
                {t.blurb}
              </p>
              <div className="mb-1">
                {t.strike && (
                  <div className={`text-xs font-bold line-through tabular ${featured ? 'text-white/50' : 'text-theme-secondary'}`}>
                    {t.strike}
                  </div>
                )}
                <div className="flex items-baseline gap-1.5">
                  <span className={`font-black tabular tracking-tight ${featured ? 'text-3xl text-white' : 'text-2xl text-theme-primary'}`}>
                    {t.price}
                  </span>
                  <span className={`text-[10px] font-bold ${featured ? 'text-white/70' : 'text-theme-secondary'}`}>once-off</span>
                </div>
                <div className={`text-[10px] font-bold tabular ${featured ? 'text-white/70' : 'text-theme-secondary'}`}>{t.approx}</div>
              </div>
              <a
                href={t.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`mt-3 mb-4 text-center py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all ${
                  featured
                    ? 'bg-purple-500 hover:bg-purple-400 text-white shadow-[0_0_20px_rgba(168,85,247,0.4)]'
                    : 'border border-purple-500/40 text-purple-400 hover:bg-purple-500/10'
                }`}
              >
                Chip in {t.price}
              </a>
              <div className={`border-t pt-3 space-y-2 mt-auto ${featured ? 'border-white/15' : 'border-theme/60'}`}>
                {perks.included.map((f) => (
                  <div key={f} className={`flex items-start gap-2 text-[11px] font-semibold ${featured ? 'text-white' : 'text-theme-primary'}`}>
                    <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-px" />
                    <span>{f}</span>
                  </div>
                ))}
                {perks.excluded.map((f) => (
                  <div key={f} className={`flex items-start gap-2 text-[11px] font-semibold ${featured ? 'text-white/40' : 'text-theme-secondary/50'}`}>
                    <Minus className="w-3.5 h-3.5 shrink-0 mt-px" />
                    <span>{f}</span>
                  </div>
                ))}
              </div>
              {perks.why && (
                <div className={`mt-3 rounded-xl p-3 ${featured ? 'bg-black/30 border border-white/10' : 'bg-black/20 border border-white/5'}`}>
                  <div className={`text-[9px] font-black uppercase tracking-widest mb-1 ${featured ? 'text-purple-200' : 'text-purple-400'}`}>
                    Why this tier?
                  </div>
                  <p className={`text-[11px] font-medium leading-relaxed ${featured ? 'text-white/85' : 'text-theme-secondary'}`}>
                    {perks.why}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </motion.div>

      <motion.div variants={fadeUp}>
        <p className="text-[11px] text-theme-secondary font-semibold text-center">
          Once-off · No subscriptions · No paywalls, ever · Processed securely by our payment partner — we never see card details
        </p>
      </motion.div>
    </motion.div>
  );
};
