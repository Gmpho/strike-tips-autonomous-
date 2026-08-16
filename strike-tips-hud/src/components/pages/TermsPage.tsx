import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, FileText, XCircle, CheckCircle, Shield, AlertTriangle, Scale, Phone, Send, ChevronDown, ChevronRight } from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };
const stagger = { animate: { transition: { staggerChildren: 0.05 } } };

const NOT_SERVICE = [
  'A bookmaker, betting platform, or gambling operator',
  'A financial advisory service',
  'A guaranteed profit system',
  'Licensed by any gambling regulator for real-money betting',
  'Affiliated with Betway, TAB, or any betting operator',
];

const RESPONSIBILITIES = [
  'Do not use the Service for real-money betting decisions',
  'Do not share the BOT_ACCESS_PIN publicly',
  'Do not automate, scrape, or reverse-engineer the Service',
  'Do not use the Service for any illegal activity',
  'Do not rely on simulated results for financial decisions',
];

const SECTIONS = [
  { id: 1, title: 'Acceptance of Terms' },
  { id: 2, title: 'What the Service Is' },
  { id: 3, title: 'What the Service Is NOT' },
  { id: 4, title: 'Eligibility' },
  { id: 5, title: 'Free Access' },
  { id: 6, title: 'Your Responsibilities' },
  { id: 7, title: 'Intellectual Property' },
  { id: 8, title: 'Disclaimer of Warranties' },
  { id: 9, title: 'Limitation of Liability' },
  { id: 10, title: 'Indemnification' },
  { id: 11, title: 'Termination' },
  { id: 12, title: 'Governing Law & Disputes' },
  { id: 13, title: 'Changes to Terms' },
  { id: 14, title: 'Related Documents' },
  { id: 15, title: 'Contact' },
];

export const TermsPage: React.FC = () => {
  const [tocOpen, setTocOpen] = useState(false);

  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      variants={stagger}
      initial="initial"
      animate="animate"
    >
      {/* Hero */}
      <motion.div variants={fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-blue-500/20 bg-gradient-to-br from-blue-500/10 via-blue-500/5 to-transparent p-6 md:p-8">
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-blue-500/10 text-white/60 hover:text-blue-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-blue-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">Terms of Service</h1>
              </div>
              <p className="text-sm text-white/60 font-medium max-w-2xl leading-relaxed">
                Strike Tips Racing Bot — Free paper-trading educational service. No subscription, payment, or financial commitment required or accepted.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Effective: June 2026</span>
                <span className="text-[10px] px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full font-bold uppercase tracking-widest text-blue-400">South Africa</span>
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Version 1.0</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Critical banner */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm font-bold text-amber-300 leading-relaxed">
            <span className="text-amber-400">Critical:</span> No real money is ever wagered, collected, held, or paid out. All &quot;bets,&quot; &quot;wins,&quot; &quot;losses,&quot; &quot;bankroll,&quot; and &quot;ROI&quot; figures are simulated paper-trading results for educational demonstration only.
          </p>
        </div>
      </motion.div>

      {/* Table of Contents (collapsible) */}
      <motion.div variants={fadeUp} className="mb-8">
        <button
          onClick={() => setTocOpen(!tocOpen)}
          className="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-white/3 border border-white/10 hover:border-blue-500/20 transition-all"
        >
          <span className="text-sm font-bold text-white/80">Table of Contents</span>
          {tocOpen ? <ChevronDown className="w-4 h-4 text-blue-400" /> : <ChevronRight className="w-4 h-4 text-white/40" />}
        </button>
        {tocOpen && (
          <div className="mt-2 p-4 rounded-xl bg-white/3 border border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-1">
            {SECTIONS.map(s => (
              <a
                key={s.id}
                href={`#section-${s.id}`}
                className="flex items-center gap-2 text-xs text-white/60 hover:text-blue-400 transition-colors py-1"
              >
                <span className="text-[10px] font-black text-blue-400/60 w-5">{s.id}.</span>
                {s.title}
              </a>
            ))}
          </div>
        )}
      </motion.div>

      {/* Sections */}
      <div className="space-y-8">
        {/* §1 */}
        <motion.section variants={fadeUp} id="section-1">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§1</span> Acceptance of Terms
          </h2>
          <p className="text-sm text-white/70 leading-relaxed">
            By accessing or using the Strike Tips Racing Bot via Telegram or the web dashboard, you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.
          </p>
        </motion.section>

        {/* §2 */}
        <motion.section variants={fadeUp} id="section-2">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§2</span> What the Service Is
          </h2>
          <div className="space-y-2">
            {[
              'Analyzes race cards, form, and odds using AI models',
              'Simulates paper-trading selections with a virtual bankroll (starting at R1,000 ZAR)',
              'Tracks simulated profit/loss and ROI for learning purposes',
              'Delivers insights via Telegram and a web dashboard (HUD)',
              'Uses a multi-agent AI architecture (local Ollama + cloud Groq/Gemini)',
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-white/70">
                <CheckCircle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                {item}
              </div>
            ))}
          </div>
        </motion.section>

        {/* §3 */}
        <motion.section variants={fadeUp} id="section-3">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§3</span> What the Service Is NOT
          </h2>
          <div className="space-y-2">
            {NOT_SERVICE.map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-rose-300/80 p-3 rounded-lg bg-rose-500/5 border border-rose-500/10">
                <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                {item}
              </div>
            ))}
          </div>
        </motion.section>

        {/* §4 */}
        <motion.section variants={fadeUp} id="section-4">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§4</span> Eligibility
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: '18+ Years', desc: 'South African legal gambling age' },
              { label: 'South Africa', desc: 'Or jurisdiction where racing data access is legal' },
              { label: 'BOT_ACCESS_PIN', desc: 'Required if PIN protection is enabled' },
            ].map((req, i) => (
              <div key={i} className="p-3 rounded-xl bg-white/3 border border-white/10">
                <div className="text-sm font-black text-blue-400 mb-1">{req.label}</div>
                <div className="text-xs text-white/55">{req.desc}</div>
              </div>
            ))}
          </div>
        </motion.section>

        {/* §5 */}
        <motion.section variants={fadeUp} id="section-5">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§5</span> Free Access
          </h2>
          <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
            <p className="text-sm text-white/70 leading-relaxed">
              The Service is currently <span className="text-emerald-400 font-bold">free to use</span>. No payment is required, no payment details are collected, and no premium tiers exist at this time. If premium features are introduced in the future, they will be governed by a separate agreement.
            </p>
          </div>
        </motion.section>

        {/* §6 */}
        <motion.section variants={fadeUp} id="section-6">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§6</span> Your Responsibilities
          </h2>
          <div className="space-y-2">
            {RESPONSIBILITIES.map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-white/70 py-2 border-b border-white/5 last:border-0">
                <Shield className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                {item}
              </div>
            ))}
          </div>
        </motion.section>

        {/* §7 */}
        <motion.section variants={fadeUp} id="section-7">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§7</span> Intellectual Property
          </h2>
          <div className="text-sm text-white/70 leading-relaxed space-y-2">
            <p>The Service, its AI models, prompts, architecture, and code are proprietary. Race data sourced from TAB4Racing, Betway, Racing Post belongs to their respective owners. Your paper-trading history and virtual bankroll data are yours to export. You may not copy, redistribute, or commercialize the Service.</p>
          </div>
        </motion.section>

        {/* §8 */}
        <motion.section variants={fadeUp} id="section-8">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§8</span> Disclaimer of Warranties
          </h2>
          <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20">
            <p className="text-xs font-bold text-amber-300/80 uppercase tracking-wide mb-2">AS IS / AS AVAILABLE</p>
            <p className="text-sm text-white/65 leading-relaxed">
              THE SERVICE IS PROVIDED WITHOUT WARRANTIES OF ANY KIND. No warranty of merchantability, fitness for purpose, accuracy, uninterrupted operation, or that simulated results will replicate real-world outcomes.
            </p>
            <p className="text-xs font-bold text-amber-400 mt-3">
              Past simulated performance does not predict future real-world results.
            </p>
          </div>
        </motion.section>

        {/* §9 */}
        <motion.section variants={fadeUp} id="section-9">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§9</span> Limitation of Liability
          </h2>
          <p className="text-sm text-white/70 leading-relaxed mb-3">
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, IN NO EVENT SHALL WE BE LIABLE FOR any direct, indirect, incidental, or consequential damages; data or profit loss; decisions based on Service output; or third-party service failures.
          </p>
          <div className="p-3 rounded-xl bg-rose-500/5 border border-rose-500/20 text-center">
            <span className="text-sm font-black text-rose-400">Our total liability shall not exceed R0 (zero) — the Service is free.</span>
          </div>
        </motion.section>

        {/* §10-15 condensed */}
        {[
          { id: 10, title: 'Indemnification', content: 'You agree to indemnify and hold us harmless from any claims, damages, or expenses arising from your violation of these Terms, your use of the Service for real-money betting, or your violation of any third-party rights.' },
          { id: 11, title: 'Termination', content: 'We may suspend or terminate your access at any time for violation of Terms, abuse, automation, or excessive load, legal or regulatory requirements, or operational shutdown. You may stop using the Service at any time by blocking the bot.' },
          { id: 12, title: 'Governing Law & Disputes', content: 'These Terms are governed by the laws of the Republic of South Africa. Any disputes shall be resolved in the courts of South Africa.' },
          { id: 13, title: 'Changes to Terms', content: 'We may update these Terms. Material changes will be announced via the Telegram bot. Continued use constitutes acceptance.' },
        ].map(section => (
          <motion.section variants={fadeUp} key={section.id} id={`section-${section.id}`}>
            <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
              <span className="text-blue-400/60 text-sm">§{section.id}</span> {section.title}
            </h2>
            <p className="text-sm text-white/70 leading-relaxed">{section.content}</p>
          </motion.section>
        ))}

        {/* §15 Contact */}
        <motion.section variants={fadeUp} id="section-15">
          <h2 className="text-base font-black text-white mb-3 flex items-center gap-2 pb-2 border-b border-white/10">
            <span className="text-blue-400/60 text-sm">§15</span> Contact
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/10">
              <Send className="w-4 h-4 text-blue-400" />
              <div>
                <div className="text-[10px] text-white/40 uppercase font-black tracking-widest">Telegram</div>
                <div className="text-sm font-bold text-white">@StrikeTipsBot</div>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/10">
              <Scale className="w-4 h-4 text-emerald-400" />
              <div>
                <div className="text-[10px] text-white/40 uppercase font-black tracking-widest">Regulator</div>
                <div className="text-sm font-bold text-white">Mpumalanga Economic Regulator</div>
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-start gap-3 p-3 rounded-xl bg-white/3 border border-white/10">
            <Phone className="w-4 h-4 text-rose-400 mt-0.5" />
            <div className="text-xs text-white/60">
              Responsible Gambling: <span className="font-bold text-white/80">0800 006 008</span> | WhatsApp <span className="font-bold text-white/80">076 675 0710</span>
            </div>
          </div>
          <p className="text-xs text-white/35 mt-4 italic">
            These Terms apply only to the Strike Tips Racing Bot paper-trading system. They do not create any right to real-money betting services.
          </p>
        </motion.section>
      </div>
    </motion.div>
  );
};
