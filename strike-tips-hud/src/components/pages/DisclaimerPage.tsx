import React from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft, AlertOctagon, CheckCircle, XCircle, Shield,
  AlertTriangle, TrendingUp, Server, BarChart2, Send, Phone
} from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.06 } } };

const WARNINGS = [
  {
    title: 'Simulated Results ≠ Real-World Outcomes',
    color: 'amber',
    points: [
      'Paper trading has no financial risk — real betting does',
      'Simulated ROI does not predict actual betting returns',
      'Market conditions, liquidity, bookmaker limits differ entirely from simulation',
    ],
  },
  {
    title: 'Not Financial Advice',
    color: 'orange',
    points: [
      'This system provides racing analysis and education, not investment advice',
      'No agent, model, or output constitutes a recommendation to bet real money',
      'Consult a licensed financial advisor for financial decisions',
    ],
  },
  {
    title: 'Not a Gambling Service',
    color: 'rose',
    points: [
      'We are not a bookmaker, not a betting platform, not a tipster service',
      'No license from any gambling regulator for real-money operations',
      'No affiliation with Betway, TAB, Hollywoodbets, or any operator',
    ],
  },
  {
    title: 'Data Sources Are Third-Party',
    color: 'blue',
    points: [
      'Odds and race data come from Betway, TAB4Racing, Racing Post',
      'We do not control their accuracy, availability, or terms of use',
      'Scraping is for informational paper-trading purposes only',
    ],
  },
];

const WHAT_WE_DO = [
  'Scrapes public race data from TAB4Racing, Betway, and Racing Post',
  'Analyzes form, odds, and conditions using a multi-agent AI swarm',
  'Simulates paper-trading selections against a virtual R1,000 bankroll',
  'Tracks simulated performance (ROI, P&L, strike rate) over time',
  'Delivers insights via Telegram and a web dashboard (HUD)',
];

const ACKNOWLEDGMENTS = [
  'This is paper trading only — no real money involved',
  'Simulated results do not predict real-world outcomes',
  'This is not financial or betting advice',
  'You are 18+ and located where this is legal',
  'You will not hold the system liable for any decisions you make',
];

const colorVariants: Record<string, { banner: string; border: string; text: string }> = {
  amber: { banner: 'bg-amber-500/10 border-amber-500/30', border: 'border-amber-500/30', text: 'text-amber-400' },
  orange: { banner: 'bg-orange-500/10 border-orange-500/30', border: 'border-orange-500/30', text: 'text-orange-400' },
  rose: { banner: 'bg-rose-500/10 border-rose-500/30', border: 'border-rose-500/30', text: 'text-rose-400' },
  blue: { banner: 'bg-blue-500/10 border-blue-500/30', border: 'border-blue-500/30', text: 'text-blue-400' },
};

export const DisclaimerPage: React.FC = () => {
  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      variants={stagger}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent p-6 md:p-8">
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-amber-500/10 text-white/60 hover:text-amber-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                  <AlertOctagon className="w-5 h-5 text-amber-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">Disclaimer</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                Strike Tips Racing Bot — Legal disclaimer for paper-trading educational system.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">June 2026</span>
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Version 1.0</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* PAPER TRADING ONLY hero banner */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="relative overflow-hidden rounded-2xl border-2 border-amber-500/50 bg-gradient-to-r from-amber-500/20 to-rose-500/10 p-6 text-center">
          <div className="absolute inset-0 opacity-5" style={{
            backgroundImage: 'repeating-linear-gradient(45deg, #f59e0b 0, #f59e0b 1px, transparent 0, transparent 50%)',
            backgroundSize: '20px 20px',
          }} />
          <div className="relative">
            <div className="text-2xl md:text-4xl font-black text-amber-400 tracking-tight mb-2">
              📢 PAPER TRADING ONLY
            </div>
            <div className="text-lg font-black text-white mb-2">NO REAL MONEY</div>
            <p className="text-sm text-white/70 max-w-xl mx-auto">
              Every figure, result, "win," "loss," "bankroll," "ROI," "profit," "stake," and "payout" shown by this system is <span className="text-amber-400 font-bold">SIMULATED</span>.
            </p>
          </div>
        </div>
      </motion.div>

      {/* What it does */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-blue-400" />
          What This System Actually Does
        </h2>
        <div className="space-y-2">
          {WHAT_WE_DO.map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/8 hover:border-blue-500/20 transition-all">
              <CheckCircle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <span className="text-sm text-white/75">{item}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 p-3 rounded-xl bg-white/3 border border-white/10">
          <p className="text-xs text-white/50 font-mono">
            Architecture: 5 specialized local models (Ollama) + cloud fallback (Groq Llama 3.3 70B, Gemini 2.0 Flash) orchestrated via intent routing with ChromaDB + Honcho dual memory.
          </p>
        </div>
      </motion.div>

      {/* Key Warnings */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          Key Warnings
        </h2>
        <div className="space-y-4">
          {WARNINGS.map((warning, i) => {
            const c = colorVariants[warning.color];
            return (
              <motion.div key={i} variants={fadeUp} className={`p-4 rounded-xl border ${c.banner}`}>
                <h3 className={`text-sm font-black mb-3 ${c.text}`}>{warning.title}</h3>
                <div className="space-y-1.5">
                  {warning.points.map((point, j) => (
                    <div key={j} className="flex items-start gap-2 text-xs text-white/65">
                      <XCircle className={`w-3.5 h-3.5 ${c.text} shrink-0 mt-0.5`} />
                      {point}
                    </div>
                  ))}
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Responsible Gambling */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-rose-400" />
          Responsible Gambling
        </h2>
        <p className="text-sm text-white/60 mb-4">If you choose to bet real money elsewhere:</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          {[
            { label: 'NRGP Helpline', value: '0800 006 008', note: '24/7 toll-free', icon: Phone },
            { label: 'WhatsApp Support', value: "'HELP' to 076 675 0710", note: '24/7', icon: Send },
            { label: 'Website', value: 'responsiblegambling.org.za', note: 'NRGP', icon: Shield },
          ].map((r, i) => {
            const Icon = r.icon;
            return (
              <div key={i} className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20 text-center">
                <Icon className="w-5 h-5 text-rose-400 mx-auto mb-2" />
                <div className="text-[9px] uppercase tracking-widest text-rose-400/60 font-black mb-1">{r.label}</div>
                <div className="text-sm font-bold text-rose-300">{r.value}</div>
                <div className="text-[10px] text-white/40 mt-0.5">{r.note}</div>
              </div>
            );
          })}
        </div>
        <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
          <p className="text-xs font-bold text-amber-300">
            <span className="text-amber-400">Warning signs:</span> Chasing losses, betting beyond means, hiding betting, borrowing to bet, emotional distress.
          </p>
          <p className="text-xs text-white/50 mt-1">
            Self-exclusion: Register with the National Central Electronic Monitoring System (NCEMS) via your bookmaker.
          </p>
        </div>
      </motion.div>

      {/* Regulatory Context */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Server className="w-5 h-5 text-purple-400" />
          Regulatory Context
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'Framework', value: 'Gambling Act 2004, Provincial Gambling Boards, POPIA', color: 'purple' },
            { label: 'Classification', value: 'Paper-trading educational tool — not regulated as gambling', color: 'emerald' },
            { label: 'Regulator Referenced', value: 'Mpumalanga Economic Regulator', color: 'blue' },
            { label: 'Age Restriction', value: '18+ only (enforced via BOT_ACCESS_PIN)', color: 'amber' },
          ].map((item, i) => (
            <div key={i} className="p-3 rounded-xl bg-white/3 border border-white/8">
              <div className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-1">{item.label}</div>
              <div className="text-sm text-white/80">{item.value}</div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* AI Model Limitations */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <BarChart2 className="w-5 h-5 text-cyan-400" />
          AI & Model Limitations
        </h2>
        <div className="space-y-2">
          {[
            { label: 'Local Models', value: 'racing_llama, racing_qwen, func_gemma, lfm_racing, ds_racing' },
            { label: 'Cloud Fallback', value: 'Groq (Llama 3.3 70B), Google (Gemini 2.0 Flash)' },
            { label: 'Hallucination Risk', value: 'AI can generate incorrect analysis — verify independently' },
            { label: 'No Insider Access', value: 'No model has access to real-time bookmaker accounts or insider information' },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/8">
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-2 shrink-0" />
              <div>
                <span className="text-sm font-bold text-white/80">{item.label}: </span>
                <span className="text-sm text-white/55">{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Acknowledgment */}
      <motion.div variants={fadeUp}>
        <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 border border-emerald-500/30">
          <h2 className="text-sm font-black text-emerald-400 mb-4">By Using Strike Tips Racing Bot, You Acknowledge:</h2>
          <div className="space-y-2">
            {ACKNOWLEDGMENTS.map((item, i) => (
              <div key={i} className="flex items-center gap-3 text-sm text-white/75">
                <div className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center shrink-0">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                </div>
                {item}
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
