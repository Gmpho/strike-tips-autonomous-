import React from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Lock, Database, Clock, Server, Shield, Globe,
  UserCheck, AlertTriangle, CheckCircle, Send, Scale
} from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.06 } } };

const DATA_COLLECTED = [
  { icon: UserCheck, label: 'Telegram User ID', desc: 'Your numeric Telegram ID', color: 'purple' },
  { icon: Database, label: 'Chat ID', desc: 'The conversation context where messages are exchanged', color: 'cyan' },
  { icon: Send, label: 'Messages You Send', desc: 'Commands, queries, and interactions with the bot', color: 'blue' },
  { icon: Lock, label: 'PIN Entry', desc: 'BOT_ACCESS_PIN for authorized access (not stored in plaintext)', color: 'amber' },
];

const DATA_GENERATED = [
  { label: 'Paper Betting History', desc: 'Simulated selections, stakes, odds, and outcomes' },
  { label: 'Virtual Bankroll Snapshots', desc: 'Balance, profit/loss, ROI over time (all simulated)' },
  { label: 'Analysis Requests', desc: 'Races you ask the system to evaluate' },
  { label: 'Learning Engine Data', desc: 'Aggregated, anonymized performance metrics' },
];

const RETENTION = [
  { type: 'Telegram messages (raw)', period: '30 days rolling', trigger: 'Auto-purge' },
  { type: 'Paper betting history', period: '2 years', trigger: 'User request or inactivity >1 year' },
  { type: 'Virtual bankroll snapshots', period: '2 years', trigger: 'User request' },
  { type: 'ChromaDB vectors', period: '1 year', trigger: 'User request' },
  { type: 'Honcho workspace data', period: '1 year', trigger: 'User request' },
  { type: 'Aggregated analytics', period: 'Indefinite', trigger: 'Never (no personal identifiers)' },
];

const PROCESSORS = [
  { processor: 'Telegram', purpose: 'Message delivery', location: 'Global', data: 'User ID, chat ID, message content' },
  { processor: 'Groq (Llama 3.3 70B)', purpose: 'AI analysis', location: 'USA', data: 'Your queries, race context' },
  { processor: 'Google (Gemini 2.0 Flash)', purpose: 'AI fallback', location: 'USA', data: 'Your queries, race context' },
  { processor: 'ChromaDB', purpose: 'Vector memory', location: 'USA', data: 'Embedded queries, responses' },
  { processor: 'Honcho', purpose: 'Session memory', location: 'USA', data: 'Conversation context' },
  { processor: 'Ollama (local)', purpose: 'Local LLM inference', location: 'Your server', data: 'None (runs locally)' },
  { processor: 'Redis', purpose: 'Caching, queues', location: 'Your server', data: 'Session state, temp data' },
];

const YOUR_RIGHTS = [
  { right: 'Access', desc: 'Request a copy of all personal data we hold about you' },
  { right: 'Rectification', desc: 'Correct inaccurate data' },
  { right: 'Deletion', desc: 'Request erasure of your data ("right to be forgotten")' },
  { right: 'Restriction', desc: 'Limit how we process your data' },
  { right: 'Portability', desc: 'Receive your data in a structured, machine-readable format' },
  { right: 'Object', desc: 'Object to processing based on legitimate interest' },
  { right: 'Complain', desc: 'Lodge a complaint with the Information Regulator (South Africa)' },
];

const SECURITY = [
  'Encryption in transit — All API calls use HTTPS/TLS',
  'Local processing — Ollama models run on your infrastructure',
  'Access control — PIN-gated bot access (BOT_ACCESS_PIN)',
  'Rate limiting — Prevents abuse and enumeration attacks',
  'No plaintext secrets — API keys stored in .env only',
  'Audit logging — All bot interactions logged for compliance review',
];

const colorMap: Record<string, string> = {
  purple: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
  cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
  blue: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  amber: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
};

export const PrivacyPage: React.FC = () => {
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
                  <Lock className="w-5 h-5 text-purple-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">Privacy Policy</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                How Strike Tips Racing Bot collects, uses, stores, and protects your personal information.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">June 2026</span>
                <span className="text-[10px] px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full font-bold uppercase tracking-widest text-emerald-400">POPIA Compliant</span>
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">South Africa</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Notice */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm font-bold text-amber-300 leading-relaxed">
            This is a <span className="text-amber-400">paper-trading only</span> educational system. No real money is ever wagered, collected, or paid out. All bankroll figures are simulated for learning purposes only.
          </p>
        </div>
      </motion.div>

      {/* Data We Collect */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Database className="w-5 h-5 text-purple-400" />
          Data We Collect
        </h2>
        <div className="mb-4">
          <div className="text-xs font-black text-white/40 uppercase tracking-widest mb-3">Information You Provide</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {DATA_COLLECTED.map((item, i) => {
              const Icon = item.icon;
              return (
                <div key={i} className={`flex items-start gap-3 p-4 rounded-xl border ${colorMap[item.color]}`}>
                  <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">{item.label}</div>
                    <div className="text-xs text-white/55 mt-0.5">{item.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div>
          <div className="text-xs font-black text-white/40 uppercase tracking-widest mb-3">Generated by the System</div>
          <div className="space-y-2">
            {DATA_GENERATED.map((item, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/8">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-400 mt-2 shrink-0" />
                <div>
                  <div className="text-sm font-bold text-white/90">{item.label}</div>
                  <div className="text-xs text-white/55">{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Legal Basis (POPIA) */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Scale className="w-5 h-5 text-emerald-400" />
          Legal Basis (POPIA)
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[400px]">
            <thead>
              <tr className="border-b border-white/10 bg-white/3">
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Processing Activity</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Lawful Basis (POPIA §11)</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['Telegram messages & commands', 'Consent (you initiated contact)'],
                ['Paper betting history', 'Legitimate interest (service improvement)'],
                ['Virtual bankroll tracking', 'Consent (opt-in via bot usage)'],
                ['AI provider queries', 'Legitimate interest (core functionality)'],
                ['ChromaDB/Honcho memory', 'Legitimate interest (context continuity)'],
                ['Aggregated analytics', 'Legitimate interest (model improvement)'],
              ].map(([activity, basis], i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                  <td className="px-4 py-3 text-sm text-white/70">{activity}</td>
                  <td className="px-4 py-3 text-xs text-emerald-400 font-medium">{basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-white/40 mt-3">
          You can withdraw consent at any time by blocking the bot or requesting data deletion.
        </p>
      </motion.div>

      {/* Data Retention */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5 text-cyan-400" />
          Data Retention
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[400px]">
            <thead>
              <tr className="border-b border-white/10 bg-white/3">
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Data Type</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Period</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Deletion Trigger</th>
              </tr>
            </thead>
            <tbody>
              {RETENTION.map((row, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                  <td className="px-4 py-3 text-sm text-white/70">{row.type}</td>
                  <td className="px-4 py-3 text-xs font-bold text-cyan-400">{row.period}</td>
                  <td className="px-4 py-3 text-xs text-white/50">{row.trigger}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Third-Party Processors */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Server className="w-5 h-5 text-blue-400" />
          Third-Party Processors
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr className="border-b border-white/10 bg-white/3">
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Processor</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Purpose</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Location</th>
                <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Data Shared</th>
              </tr>
            </thead>
            <tbody>
              {PROCESSORS.map((row, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                  <td className="px-4 py-3 text-sm font-bold text-white/80">{row.processor}</td>
                  <td className="px-4 py-3 text-xs text-white/60">{row.purpose}</td>
                  <td className="px-4 py-3 text-xs text-blue-400 font-medium">{row.location}</td>
                  <td className="px-4 py-3 text-xs text-white/50">{row.data}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
          <p className="text-xs font-bold text-emerald-300">
            No payment processors — Free, paper-trading-only service. No Stripe, Paystack, or payment data collected.
          </p>
        </div>
      </motion.div>

      {/* Your Rights */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <UserCheck className="w-5 h-5 text-amber-400" />
          Your Rights (POPIA Section 5)
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {YOUR_RIGHTS.map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/8 hover:border-amber-500/20 transition-all">
              <CheckCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-bold text-white">{item.right}</div>
                <div className="text-xs text-white/55 mt-0.5">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 p-3 rounded-xl bg-purple-500/5 border border-purple-500/20">
          <p className="text-xs text-white/60">
            To exercise any right: Send <code className="text-purple-400 font-mono">/privacy</code> to the bot or email the administrator. We respond within 30 days per POPIA.
          </p>
        </div>
      </motion.div>

      {/* Security */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-emerald-400" />
          Security Measures
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {SECURITY.map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-white/65 p-3 rounded-xl bg-white/3 border border-white/8">
              <Shield className="w-3 h-3 text-emerald-400 shrink-0" />
              {item}
            </div>
          ))}
        </div>
      </motion.div>

      {/* International Transfers */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-blue-400" />
          International Transfers
        </h2>
        <p className="text-sm text-white/65 leading-relaxed">
          Your data may be processed outside South Africa by Groq (USA), Google Gemini (USA), ChromaDB Cloud (USA), and Honcho (USA). These transfers rely on <span className="text-blue-400 font-bold">adequacy decisions</span> or <span className="text-blue-400 font-bold">standard contractual clauses</span>. By using the bot, you consent to these transfers.
        </p>
      </motion.div>

      {/* Children's Privacy */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-black text-rose-400 mb-1">Children's Privacy</div>
            <p className="text-xs text-white/65 leading-relaxed">
              No persons under 18 are permitted to use this service. The bot enforces this via BOT_ACCESS_PIN shared only with verified adults. If you believe a minor has accessed the bot, contact us immediately.
            </p>
          </div>
        </div>
      </motion.div>

      {/* Contact */}
      <motion.div variants={fadeUp}>
        <div className="p-4 rounded-xl bg-white/3 border border-white/10">
          <h2 className="text-sm font-black text-white/80 mb-3">Contact & Regulator</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { label: 'Data Administrator', value: 'Strike Tips System Administrator', icon: UserCheck, color: 'text-purple-400' },
              { label: 'Channel', value: '@StrikeTipsBot → /privacy', icon: Send, color: 'text-blue-400' },
              { label: 'Regulator (SA)', value: 'Information Regulator', icon: Scale, color: 'text-emerald-400' },
              { label: 'Regulator URL', value: 'inforegulator.org.za', icon: Globe, color: 'text-cyan-400' },
            ].map((item, i) => {
              const Icon = item.icon;
              return (
                <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/8">
                  <Icon className={`w-4 h-4 ${item.color} shrink-0`} />
                  <div>
                    <div className="text-[10px] text-white/40 uppercase font-black tracking-widest">{item.label}</div>
                    <div className="text-sm font-bold text-white/80">{item.value}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
