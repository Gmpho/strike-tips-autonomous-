import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Heart, Phone, Send, Globe, CheckSquare, Square,
  AlertTriangle, Shield, Scale, Users, MapPin, CheckCircle
} from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.06 } } };

const WARNING_SIGNS = {
  Behavioural: [
    'Chasing losses (betting more to recover)',
    'Betting beyond affordable limits',
    'Hiding betting activity from family/friends',
    'Borrowing money to bet',
    'Lying about gambling extent',
    'Neglecting work, family, or obligations',
    'Gambling to escape stress/anxiety/depression',
  ],
  Emotional: [
    'Restless/irritable when not gambling',
    'Preoccupied with past/future bets',
    'Guilt, shame, or anxiety after betting',
    "Using gambling to 'feel normal'",
  ],
  Financial: [
    'Unpaid bills due to gambling losses',
    'Maxed credit cards / payday loans',
    'Selling possessions to fund betting',
    "Asking others for 'bailout' money",
  ],
};

const SELF_PROTECTION = [
  { tool: 'National Self-Exclusion (NCEMS)', provider: 'All licensed bookmakers', access: 'Ask any bookmaker to register you' },
  { tool: 'Deposit Limits', provider: 'Betway, Hollywoodbets, TAB, etc.', access: 'Account settings → Responsible Gambling' },
  { tool: 'Session Time Limits', provider: 'Most SA operators', access: 'Account settings' },
  { tool: 'Reality Checks', provider: 'Betway, Hollywoodbets', access: 'Pop-up reminders during play' },
  { tool: 'Account Closure', provider: 'Any operator', access: 'Contact support' },
];

const PROVINCIAL_REGULATORS = [
  { province: 'Gauteng', body: 'Gauteng Gambling Board' },
  { province: 'Western Cape', body: 'Western Cape Gambling & Racing Board' },
  { province: 'KwaZulu-Natal', body: 'KZN Gaming & Betting Board' },
  { province: 'Mpumalanga', body: 'Mpumalanga Economic Regulator ★' },
  { province: 'Eastern Cape', body: 'Eastern Cape Gambling Board' },
  { province: 'Free State', body: 'Free State Gambling & Liquor Authority' },
  { province: 'Limpopo', body: 'Limpopo Gambling Board' },
  { province: 'North West', body: 'North West Gambling Board' },
  { province: 'Northern Cape', body: 'Northern Cape Gambling Board' },
];

const DOS = [
  'Set a strict budget before starting — treat as entertainment cost',
  'Use deposit limits on every operator account',
  'Track every bet in a spreadsheet',
  'Take regular breaks (set timers)',
  'Bet only what you can afford to lose',
];

const DONTS = [
  'Chase losses',
  'Bet under influence (alcohol, drugs, emotional distress)',
  'Borrow to bet',
  'Treat gambling as income source',
  "Bet on unfamiliar sports/markets 'for action'",
];

export const ResponsiblePage: React.FC = () => {
  const [checked, setChecked] = useState<Set<string>>(new Set());

  const toggleCheck = (key: string) => {
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const totalChecked = checked.size;

  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      variants={stagger}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-rose-500/30 bg-gradient-to-br from-rose-500/15 via-rose-500/5 to-transparent p-6 md:p-8">
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-rose-500/10 text-white/60 hover:text-rose-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center">
                  <Heart className="w-5 h-5 text-rose-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">Responsible Gambling</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                Strike Tips Racing Bot is a paper-trading educational system only. No real money is ever wagered, collected, or paid out. <span className="text-rose-400 font-bold">If you or someone you know needs help, use the contacts below immediately.</span>
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Immediate Help — Top priority */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="p-1 rounded-2xl bg-gradient-to-r from-rose-500/30 via-rose-500/10 to-rose-500/30">
          <div className="p-5 rounded-xl bg-rose-500/10">
            <div className="flex items-center gap-2 mb-4">
              <Phone className="w-5 h-5 text-rose-400" />
              <h2 className="text-lg font-black text-rose-400">🚨 Immediate Help</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { label: 'NRGP Helpline', contact: '0800 006 008', note: '24/7 toll-free', icon: Phone },
                { label: 'WhatsApp Counselling', contact: "'HELP' to 076 675 0710", note: '24/7', icon: Send },
                { label: 'Website', contact: 'responsiblegambling.org.za', note: 'Always available', icon: Globe },
                { label: 'Email', contact: 'help@responsiblegambling.org.za', note: 'Business hours', icon: Send },
              ].map((item, i) => {
                const Icon = item.icon;
                return (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20">
                    <Icon className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
                    <div>
                      <div className="text-[10px] font-black text-rose-400/60 uppercase tracking-widest">{item.label}</div>
                      <div className="text-sm font-bold text-white">{item.contact}</div>
                      <div className="text-[10px] text-white/40">{item.note}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Warning Signs Self-Check */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-black text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            Warning Signs Checklist
          </h2>
          {totalChecked > 0 && (
            <div className={`text-xs font-black px-3 py-1 rounded-full border ${
              totalChecked >= 3 ? 'bg-rose-500/20 border-rose-500/40 text-rose-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            }`}>
              {totalChecked} checked {totalChecked >= 3 ? '— Seek help now' : ''}
            </div>
          )}
        </div>
        <p className="text-xs text-white/50 mb-4">Tick any that apply to you or someone you know. If 3+ apply, seek help immediately.</p>
        <div className="space-y-6">
          {Object.entries(WARNING_SIGNS).map(([category, signs]) => (
            <div key={category}>
              <div className="text-xs font-black text-amber-400/70 uppercase tracking-widest mb-2">{category}</div>
              <div className="space-y-2">
                {signs.map((sign, i) => {
                  const key = `${category}-${i}`;
                  const isChecked = checked.has(key);
                  return (
                    <button
                      key={key}
                      onClick={() => toggleCheck(key)}
                      className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                        isChecked
                          ? 'bg-amber-500/15 border-amber-500/40'
                          : 'bg-white/3 border-white/8 hover:border-amber-500/20'
                      }`}
                    >
                      {isChecked
                        ? <CheckSquare className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        : <Square className="w-4 h-4 text-white/30 shrink-0 mt-0.5" />
                      }
                      <span className={`text-sm ${isChecked ? 'text-amber-300' : 'text-white/65'}`}>{sign}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        {totalChecked >= 3 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-4 p-4 rounded-xl bg-rose-500/20 border-2 border-rose-500/50 text-center"
          >
            <div className="text-rose-400 font-black text-lg mb-1">Please Seek Help Now</div>
            <div className="text-white/70 text-sm">Call <span className="font-bold text-rose-400">0800 006 008</span> — Free, confidential, 24/7</div>
          </motion.div>
        )}
      </motion.div>

      {/* Self-Protection Tools */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-emerald-400" />
          Self-Protection Tools
        </h2>
        <div className="mb-3">
          <div className="text-xs font-black text-white/40 uppercase tracking-widest mb-3">South African Options</div>
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full min-w-[400px]">
              <thead>
                <tr className="border-b border-white/10 bg-white/3">
                  <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Tool</th>
                  <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">Provider</th>
                  <th className="text-left px-4 py-3 text-[10px] font-black uppercase tracking-widest text-white/40">How to Access</th>
                </tr>
              </thead>
              <tbody>
                {SELF_PROTECTION.map((row, i) => (
                  <tr key={i} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                    <td className="px-4 py-3 text-sm font-bold text-emerald-400">{row.tool}</td>
                    <td className="px-4 py-3 text-xs text-white/60">{row.provider}</td>
                    <td className="px-4 py-3 text-xs text-white/50">{row.access}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-4">
          <div className="text-xs font-black text-white/40 uppercase tracking-widest mb-3">Strike Tips Bot Controls</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[
              'PIN-gated access — Only authorised users (BOT_ACCESS_PIN)',
              'Paper-trading only — Zero financial risk in the bot',
              'Hard bankroll limits — 5% max bet, 20% daily loss cap (cannot override)',
              'No real-money integration — No deposit/withdrawal possible',
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-white/65 p-3 rounded-xl bg-white/3 border border-white/8">
                <CheckCircle className="w-3 h-3 text-emerald-400 shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Do's and Don'ts */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-purple-400" />
          If You Choose to Bet Real Money
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-black text-emerald-400 uppercase tracking-widest mb-3">✓ DO</div>
            <div className="space-y-2">
              {DOS.map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-white/70 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/15">
                  <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs font-black text-rose-400 uppercase tracking-widest mb-3">✗ DON'T</div>
            <div className="space-y-2">
              {DONTS.map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-white/70 p-3 rounded-xl bg-rose-500/5 border border-rose-500/15">
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* For Family & Friends */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Users className="w-5 h-5 text-blue-400" />
          For Family & Friends
        </h2>
        <div className="space-y-2 mb-4">
          {[
            'Listen without judgment — shame drives secrecy',
            'Encourage professional help — NRGP counsellors are free',
            "Don't enable — don't pay debts, don't cover losses",
            'Set boundaries — protect your own finances',
            'Self-care — Gam-Anon SA supports affected others',
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/8">
              <div className="w-5 h-5 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shrink-0 text-[10px] font-black text-blue-400">{i + 1}</div>
              <span className="text-sm text-white/70">{item}</span>
            </div>
          ))}
        </div>
        <div className="p-3 rounded-xl bg-blue-500/5 border border-blue-500/20">
          <p className="text-xs text-white/60">
            <span className="font-bold text-blue-400">Gam-Anon SA:</span> gamanon.org.za | WhatsApp support groups available
          </p>
        </div>
      </motion.div>

      {/* Provincial Regulators */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <MapPin className="w-5 h-5 text-amber-400" />
          South African Legal Context
        </h2>
        <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 mb-4">
          <p className="text-xs text-amber-300 font-bold">Gambling Act 2004: Legal age 18+. Licensed operators only (provincial boards). Online sports betting legal with licence.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PROVINCIAL_REGULATORS.map((reg, i) => (
            <div key={i} className={`flex items-start gap-2 p-3 rounded-xl border transition-all ${reg.body.includes('★') ? 'bg-purple-500/10 border-purple-500/30' : 'bg-white/3 border-white/8'}`}>
              <Scale className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${reg.body.includes('★') ? 'text-purple-400' : 'text-white/40'}`} />
              <div>
                <div className="text-[10px] font-black text-white/40 uppercase tracking-widest">{reg.province}</div>
                <div className={`text-xs font-bold ${reg.body.includes('★') ? 'text-purple-400' : 'text-white/70'}`}>{reg.body.replace(' ★', '')}</div>
                {reg.body.includes('★') && <div className="text-[9px] text-purple-400/60 mt-0.5">Referenced by this bot</div>}
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Footer message */}
      <motion.div variants={fadeUp}>
        <div className="p-6 rounded-2xl bg-gradient-to-br from-rose-500/10 to-rose-500/5 border border-rose-500/30 text-center">
          <Heart className="w-8 h-8 text-rose-400 mx-auto mb-3" />
          <p className="text-lg font-black text-white mb-1">Winners know when to stop.</p>
          <p className="text-sm text-white/60">Help is <span className="text-emerald-400 font-bold">free</span>, <span className="text-blue-400 font-bold">confidential</span>, and available <span className="text-amber-400 font-bold">24/7</span>.</p>
          <div className="flex justify-center gap-4 mt-4">
            <div className="text-center">
              <div className="text-[10px] text-white/40 uppercase font-black tracking-widest mb-1">NRGP Helpline</div>
              <div className="text-lg font-black text-rose-400">0800 006 008</div>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
