import React from 'react';
import { motion } from 'framer-motion';
import {
  BookOpen, ArrowLeft, Database, Brain, TrendingUp, Shield,
  CheckCircle, Terminal, Globe, Zap, AlertTriangle, Phone,
  Activity, BarChart2, Bot
} from 'lucide-react';

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
};

const stagger = {
  animate: { transition: { staggerChildren: 0.07 } },
};

const PIPELINE_STEPS = [
  { icon: Database, color: 'cyan', label: 'Data Scrapers', desc: 'Fetch race cards & odds from TAB4Racing, Betway, Racing Post' },
  { icon: Brain, color: 'purple', label: 'Form Analyzer', desc: 'Evaluates horse/jockey/trainer stats, track conditions, distance suitability' },
  { icon: BarChart2, color: 'emerald', label: 'Edge Calculator', desc: 'Compares implied probability vs. model probability' },
  { icon: Shield, color: 'amber', label: 'Bankroll Governor', desc: 'Kelly criterion: 5% max bet, 20% daily loss limit enforced' },
  { icon: CheckCircle, color: 'rose', label: 'Result Tracker', desc: 'Auto-settles after races via DuckDuckGo → fuzzy match' },
];

const AGENTS = [
  { model: 'racing_llama', role: 'Router + Synthesizer', specialty: 'Fast, all tools', color: 'purple' },
  { model: 'racing_qwen', role: 'Fast Reads', specialty: 'Account summary, search', color: 'cyan' },
  { model: 'func_gemma', role: 'Write Ops', specialty: 'Record selections, update results', color: 'emerald' },
  { model: 'lfm_racing', role: 'Deep Analysis', specialty: 'Race evaluation, daily scan', color: 'blue' },
  { model: 'ds_racing', role: 'Reasoning', specialty: 'Probability edge calculation', color: 'amber' },
  { model: 'Groq Llama 3.3 70B', role: 'Cloud Fallback', specialty: 'Complex reasoning', color: 'pink' },
  { model: 'Gemini 2.0 Flash', role: 'Cloud Fallback', specialty: 'Speed', color: 'indigo' },
];

const COMMANDS = [
  { cmd: '/start', desc: 'Welcome + PIN prompt' },
  { cmd: '/races', desc: "Today's race cards" },
  { cmd: '/selections', desc: 'Current paper-trading picks' },
  { cmd: '/bankroll', desc: 'Virtual balance & P&L' },
  { cmd: '/results', desc: 'Settled results (today)' },
  { cmd: '/stats', desc: 'ROI, strike rate, best tracks' },
  { cmd: '/help', desc: 'Command list' },
];

const METRICS = [
  { label: 'Edge %', formula: '(Model Probability × Decimal Odds) − 1', color: 'emerald' },
  { label: 'Stake', formula: 'Bankroll × Kelly Fraction × Edge (capped at 5%)', color: 'purple' },
  { label: 'Confidence', formula: 'High / Medium / Low based on data quality', color: 'amber' },
];

const colorMap: Record<string, string> = {
  cyan: 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400',
  purple: 'bg-purple-500/10 border-purple-500/30 text-purple-400',
  emerald: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
  amber: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  rose: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
  blue: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  pink: 'bg-pink-500/10 border-pink-500/30 text-pink-400',
  indigo: 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400',
};

export const HowToBetPage: React.FC = () => {
  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      variants={stagger}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-purple-500/20 bg-gradient-to-br from-purple-500/10 via-purple-500/5 to-transparent p-6 md:p-8">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-600/10 to-transparent pointer-events-none" />
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-purple-500/10 text-white/60 hover:text-purple-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-purple-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">How to Bet</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                Strike Tips Racing Bot is a <span className="text-purple-400 font-bold">paper-trading educational system</span> — it simulates betting selections against a virtual R1,000 bankroll. No real money is ever wagered, collected, or paid out.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Effective: June 2026</span>
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Version 1.0</span>
                <span className="text-[10px] px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full font-bold uppercase tracking-widest text-emerald-400">South Africa</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Warning Banner */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm font-bold text-amber-300 leading-relaxed">
            <span className="text-amber-400">PAPER TRADING ONLY</span> — No real money involved. Simulated results ≠ real-world outcomes. Not financial or betting advice. Educational use only.
          </p>
        </div>
      </motion.div>

      {/* Section: What You'll See */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5 text-purple-400" />
          What You'll See
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { label: 'Daily Race Cards', desc: 'SA tracks: Turffontein, Vaal, Fairview, Scottsville, Kenilworth, Durbanville, Greyville' },
            { label: 'AI Analysis', desc: 'Multi-agent swarm (5 local models + cloud fallback)' },
            { label: 'Edge Calculations', desc: 'Probability vs. market odds comparison' },
            { label: 'Simulated Stakes', desc: 'Kelly fraction (half-Kelly for safety) suggestions' },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] hover:border-purple-500/30 transition-all">
              <div className="w-2 h-2 rounded-full bg-purple-400 mt-2 shrink-0" />
              <div>
                <div className="text-sm font-bold text-white mb-1">{item.label}</div>
                <div className="text-xs text-white/60 leading-relaxed">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Selection Format */}
        <div className="mt-4 p-4 rounded-xl bg-black/40 border border-white/10 font-mono">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/40 mb-2">Selection Format</div>
          <div className="text-sm text-emerald-400 font-mono">
            Horse Name | Track Race# | Odds | Edge % | Stake (R) | Confidence
          </div>
        </div>
      </motion.div>

      {/* Section: Data Pipeline */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Database className="w-5 h-5 text-cyan-400" />
          Data Pipeline
        </h2>
        <div className="relative">
          <div className="absolute left-6 top-6 bottom-6 w-px bg-gradient-to-b from-cyan-500/40 via-purple-500/40 to-emerald-500/40 hidden md:block" />
          <div className="space-y-3">
            {PIPELINE_STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <motion.div
                  key={i}
                  variants={fadeUp}
                  className="relative flex items-start gap-4 p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] hover:border-purple-500/20 transition-all group"
                >
                  <div className={`w-10 h-10 rounded-xl border flex items-center justify-center shrink-0 z-10 ${colorMap[step.color]}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-black text-white/30 uppercase tracking-widest">Step {i + 1}</span>
                    </div>
                    <div className="text-sm font-bold text-white">{step.label}</div>
                    <div className="text-xs text-white/60 mt-0.5 leading-relaxed">{step.desc}</div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </motion.div>

      {/* Section: AI Swarm */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Bot className="w-5 h-5 text-purple-400" />
          AI Agent Swarm
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.03]">
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Model</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Role</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Specialty</th>
              </tr>
            </thead>
            <tbody>
              {AGENTS.map((agent, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/[0.03] transition-colors">
                  <td className="px-4 py-3">
                    <code className={`text-xs font-mono px-2 py-0.5 rounded border ${colorMap[agent.color]}`}>
                      {agent.model}
                    </code>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-white/80">{agent.role}</td>
                  <td className="px-4 py-3 text-xs text-white/50">{agent.specialty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Section: Key Metrics */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          Key Metrics
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {METRICS.map((m, i) => (
            <div key={i} className="p-4 rounded-xl bg-white/[0.03] border border-white/10">
              <div className={`text-lg font-black mb-2 ${m.color === 'emerald' ? 'text-emerald-400' : m.color === 'purple' ? 'text-purple-400' : 'text-amber-400'}`}>{m.label}</div>
              <div className="text-xs text-white/60 leading-relaxed font-mono">{m.formula}</div>
            </div>
          ))}
        </div>

        {/* Example */}
        <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
          <div className="text-[10px] font-black uppercase tracking-widest text-emerald-400/60 mb-2">Example</div>
          <code className="text-sm font-mono text-emerald-300 block mb-3">
            Reflective | Vaal R8 | 5.50 | +12.4% | R42 | HIGH
          </code>
          <div className="space-y-1 text-xs text-white/60">
            <p>→ Model gives 20.4% win probability vs. market 18.2% (5.50 odds)</p>
            <p>→ Kelly stake = R1,000 × 0.5 × 0.124 = R62 → capped at 5% = R50 → R42 after rounding</p>
          </div>
        </div>
      </motion.div>

      {/* Section: Telegram Commands */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-blue-400" />
          Telegram Bot Commands
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {COMMANDS.map((cmd, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.08] hover:border-blue-500/20 transition-all">
              <code className="text-xs font-mono px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400 shrink-0">{cmd.cmd}</code>
              <span className="text-xs text-white/60">{cmd.desc}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Section: Web Dashboard */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-purple-400" />
          Web Dashboard (HUD)
        </h2>
        <div className="p-4 rounded-xl bg-purple-500/5 border border-purple-500/20">
          <div className="text-xs font-mono text-purple-400 mb-3">https://strike-tips-hud.vercel.app</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[
              'Live race cards with AI selections',
              'Bankroll history chart',
              'Agent pipeline status',
              'Market movers & ATR predictors',
              'System vitals & logs',
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-white/70">
                <Zap className="w-3 h-3 text-purple-400 shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Section: Responsible Gambling */}
      <motion.div variants={fadeUp}>
        <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20">
          <h2 className="text-sm font-black text-rose-400 mb-3 flex items-center gap-2">
            <Phone className="w-4 h-4" />
            Responsible Gambling
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: 'Helpline', value: '0800 006 008', note: '24/7 toll-free' },
              { label: 'WhatsApp', value: "'HELP' to 076 675 0710", note: '24/7 support' },
              { label: 'Website', value: 'responsiblegambling.org.za', note: 'NRGP' },
            ].map((r, i) => (
              <div key={i} className="text-center p-3 rounded-xl bg-rose-500/5 border border-rose-500/10">
                <div className="text-[9px] uppercase tracking-widest text-rose-400/60 font-black mb-1">{r.label}</div>
                <div className="text-sm font-bold text-rose-300">{r.value}</div>
                <div className="text-[10px] text-white/40 mt-0.5">{r.note}</div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
