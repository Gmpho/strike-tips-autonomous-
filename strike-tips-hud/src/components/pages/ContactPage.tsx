import React from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Mail, Send, Phone, Globe, Shield, Scale, MessageSquare,
  Bot, Heart, ExternalLink, Zap
} from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.07 } } };

export const ContactPage: React.FC = () => {
  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      variants={stagger}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-500/10 via-purple-500/5 to-transparent p-6 md:p-8">
          <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-indigo-500/10 text-white/60 hover:text-indigo-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-indigo-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">Contact</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                Strike Tips Racing Bot — Get in touch with the system administrator or access responsible gambling support.
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Primary Contact */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Bot className="w-5 h-5 text-purple-400" />
          System Administrator
        </h2>
        <div className="relative overflow-hidden rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-500/10 via-purple-500/5 to-transparent p-6">
          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-2xl pointer-events-none" />
          <div className="relative">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-purple-500/20 border border-purple-500/40 flex items-center justify-center">
                <Bot className="w-7 h-7 text-purple-400" />
              </div>
              <div>
                <div className="text-lg font-black text-white">Strike Tips Bot</div>
                <div className="text-sm text-purple-400 font-bold">@Striketips_bot</div>
                <div className="flex items-center gap-1.5 mt-1">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px] shadow-emerald-400" />
                  <span className="text-xs text-white/50 font-medium">Active on Telegram</span>
                </div>
              </div>
            </div>
            <p className="text-sm text-white/65 leading-relaxed mb-5">
              The primary contact channel for Strike Tips Racing Bot is via Telegram. Message the bot directly for technical support, configuration help, or to report issues.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { cmd: '/help', desc: 'Command list & general help' },
                { cmd: '/privacy', desc: 'Privacy policy information' },
                { cmd: '/terms', desc: 'Terms of service information' },
                { cmd: '/disclaimer', desc: 'Disclaimer information' },
                { cmd: '/responsible', desc: 'Responsible gambling help' },
                { cmd: '/config', desc: 'Configuration & settings' },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/8 hover:border-purple-500/30 transition-all">
                  <code className="text-xs font-mono px-2.5 py-1 bg-purple-500/15 border border-purple-500/25 rounded-lg text-purple-400 shrink-0">{item.cmd}</code>
                  <span className="text-xs text-white/60">{item.desc}</span>
                </div>
              ))}
            </div>
            <a
              href="https://web.telegram.org/k/#@Striketips_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-5 w-full flex items-center justify-center gap-2 py-3 px-6 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 rounded-xl text-purple-300 hover:text-white transition-all font-bold text-sm"
            >
              <Send className="w-4 h-4" />
              Open in Telegram
              <ExternalLink className="w-3 h-3 opacity-60" />
            </a>
          </div>
        </div>
      </motion.div>

      {/* Web Dashboard */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5 text-cyan-400" />
          Web Dashboard
        </h2>
        <div className="p-5 rounded-2xl border border-cyan-500/20 bg-cyan-500/5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center shrink-0">
              <Globe className="w-5 h-5 text-cyan-400" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-black text-white mb-1">Strike Tips HUD</div>
              <a
                href="https://strike-tips-hud.vercel.app"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-cyan-400 hover:text-cyan-300 font-mono transition-colors flex items-center gap-1"
              >
                https://strike-tips-hud.vercel.app
                <ExternalLink className="w-3 h-3" />
              </a>
              <p className="text-xs text-white/55 mt-2 leading-relaxed">
                Access the live racing intelligence dashboard for race cards, bankroll tracking, AI agents, and analytics.
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                {['Race Cards', 'Bankroll', 'AI Agents', 'Analytics', 'Logs'].map(feature => (
                  <span key={feature} className="text-[9px] px-2 py-1 bg-cyan-500/10 border border-cyan-500/20 rounded-full font-bold text-cyan-400 uppercase tracking-widest">
                    {feature}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Responsible Gambling Emergency */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Heart className="w-5 h-5 text-rose-400" />
          Responsible Gambling Support
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          {[
            {
              label: 'NRGP 24/7 Helpline',
              value: '0800 006 008',
              note: 'Free, toll-free, 24 hours',
              icon: Phone,
              color: 'rose',
            },
            {
              label: 'WhatsApp Support',
              value: "'HELP' to 076 675 0710",
              note: '24/7 counselling available',
              icon: Send,
              color: 'emerald',
            },
            {
              label: 'Online Help',
              value: 'responsiblegambling.org.za',
              note: 'National Responsible Gambling Programme',
              icon: Globe,
              color: 'blue',
            },
            {
              label: 'Email',
              value: 'help@responsiblegambling.org.za',
              note: 'Business hours response',
              icon: Mail,
              color: 'purple',
            },
          ].map((item, i) => {
            const Icon = item.icon;
            return (
              <div key={i} className={`p-4 rounded-xl border ${
                item.color === 'rose' ? 'bg-rose-500/10 border-rose-500/30' :
                item.color === 'emerald' ? 'bg-emerald-500/10 border-emerald-500/30' :
                item.color === 'blue' ? 'bg-blue-500/10 border-blue-500/30' :
                'bg-purple-500/10 border-purple-500/30'
              }`}>
                <Icon className={`w-5 h-5 mb-2 ${
                  item.color === 'rose' ? 'text-rose-400' :
                  item.color === 'emerald' ? 'text-emerald-400' :
                  item.color === 'blue' ? 'text-blue-400' :
                  'text-purple-400'
                }`} />
                <div className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-1">{item.label}</div>
                <div className={`text-sm font-black ${
                  item.color === 'rose' ? 'text-rose-300' :
                  item.color === 'emerald' ? 'text-emerald-300' :
                  item.color === 'blue' ? 'text-blue-300' :
                  'text-purple-300'
                }`}>{item.value}</div>
                <div className="text-[10px] text-white/40 mt-1">{item.note}</div>
              </div>
            );
          })}
        </div>
      </motion.div>

      {/* Regulator Reference */}
      <motion.div variants={fadeUp} className="mb-8">
        <h2 className="text-lg font-black text-white mb-4 flex items-center gap-2">
          <Scale className="w-5 h-5 text-amber-400" />
          Regulatory Reference
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20">
            <Scale className="w-5 h-5 text-amber-400 mb-2" />
            <div className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-1">Regulator</div>
            <div className="text-sm font-bold text-amber-300">Mpumalanga Economic Regulator</div>
            <div className="text-xs text-white/40 mt-1">Provincial gambling authority</div>
          </div>
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
            <Shield className="w-5 h-5 text-emerald-400 mb-2" />
            <div className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-1">Classification</div>
            <div className="text-sm font-bold text-emerald-300">Paper-Trading Educational Tool</div>
            <div className="text-xs text-white/40 mt-1">Not a gambling service</div>
          </div>
          <div className="p-4 rounded-xl bg-blue-500/5 border border-blue-500/20">
            <Scale className="w-5 h-5 text-blue-400 mb-2" />
            <div className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-1">Data Regulator (POPIA)</div>
            <div className="text-sm font-bold text-blue-300">Information Regulator SA</div>
            <a href="https://inforegulator.org.za" target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:underline mt-1 flex items-center gap-1">
              inforegulator.org.za <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </div>
          <div className="p-4 rounded-xl bg-purple-500/5 border border-purple-500/20">
            <Zap className="w-5 h-5 text-purple-400 mb-2" />
            <div className="text-[10px] font-black text-white/40 uppercase tracking-widest mb-1">Jurisdiction</div>
            <div className="text-sm font-bold text-purple-300">Republic of South Africa</div>
            <div className="text-xs text-white/40 mt-1">Governed under SA law</div>
          </div>
        </div>
      </motion.div>

      {/* Bottom banner */}
      <motion.div variants={fadeUp}>
        <div className="p-5 rounded-2xl bg-gradient-to-br from-white/3 to-white/1 border border-white/10 text-center">
          <p className="text-xs text-white/40 leading-relaxed">
            Strike Tips Racing Bot is a free, paper-trading educational tool. No real money is ever wagered, collected, or paid out. For technical issues, message <span className="text-purple-400 font-bold">@Striketips_bot</span> on Telegram. For gambling-related concerns, contact the <span className="text-rose-400 font-bold">NRGP at 0800 006 008</span>.
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
};
