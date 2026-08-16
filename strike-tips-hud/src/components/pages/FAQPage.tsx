import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HelpCircle, ArrowLeft, ChevronDown, Search, MessageSquare, Cpu, PiggyBank, Send, Scale, Phone } from 'lucide-react';

const fadeUp = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

const FAQ_SECTIONS = [
  {
    category: 'General',
    icon: HelpCircle,
    color: 'purple',
    items: [
      {
        q: 'What is Strike Tips Racing Bot?',
        a: 'An educational paper-trading system for South African horse racing that uses AI to analyze races, calculate edges, and simulate selections against a virtual R1,000 bankroll. No real money is involved.',
      },
      {
        q: 'Is this a betting platform?',
        a: 'No. It\'s a learning tool. No bets are placed, no money is deposited/withdrawn, no odds are offered for real wagering.',
      },
      {
        q: 'Who can use it?',
        a: 'Adults (18+) in South Africa (or jurisdictions where accessing racing data is legal). Access requires the BOT_ACCESS_PIN.',
      },
      {
        q: 'How much does it cost?',
        a: 'Free. No subscription, no premium tiers, no payment details collected.',
      },
    ],
  },
  {
    category: 'Technical',
    icon: Cpu,
    color: 'cyan',
    items: [
      {
        q: 'Which AI models does it use?',
        a: 'Local (Ollama): racing_llama, racing_qwen, func_gemma, lfm_racing, ds_racing. Cloud fallback: Groq (Llama 3.3 70B), Google (Gemini 2.0 Flash).',
      },
      {
        q: 'Where does race data come from?',
        a: 'Public sources: TAB4Racing, Betway, Racing Post. Scraped for informational paper-trading purposes only.',
      },
      {
        q: 'How is my data stored?',
        a: 'Telegram: Messages, user ID, chat ID. ChromaDB Cloud: Vector embeddings. Honcho: Session memory. Redis: Caching, queues. Local: Ollama runs on your infrastructure — no data leaves for local inference.',
      },
      {
        q: 'Is my data private?',
        a: 'Yes. POPIA-compliant. No marketing, no data sales. See Privacy Policy.',
      },
    ],
  },
  {
    category: 'Paper Trading',
    icon: PiggyBank,
    color: 'emerald',
    items: [
      {
        q: "What's the starting bankroll?",
        a: 'R1,000 ZAR (virtual/fake money).',
      },
      {
        q: 'How are stakes calculated?',
        a: 'Half-Kelly criterion: Stake = Bankroll × 0.5 × Edge, capped at 5% of bankroll per bet.',
      },
      {
        q: 'How are results settled?',
        a: 'Automatically via ResultTracker: searches DuckDuckGo for results → scrapes → fuzzy matches winner → updates virtual P&L.',
      },
      {
        q: 'Can I reset my bankroll?',
        a: 'Yes, via Settings in the HUD or /config API.',
      },
    ],
  },
  {
    category: 'Telegram Bot',
    icon: Send,
    color: 'blue',
    items: [
      {
        q: 'How do I start?',
        a: 'Message @StrikeTipsBot on Telegram, enter the BOT_ACCESS_PIN when prompted.',
      },
      {
        q: 'What commands are available?',
        a: '/start, /races, /selections, /bankroll, /results, /stats, /help, /privacy, /terms, /disclaimer',
      },
      {
        q: "Why do messages say [PAPER MODE]?",
        a: 'Every message is prefixed to reinforce: no real money is ever wagered.',
      },
      {
        q: 'Bot not responding?',
        a: 'Check PIN is correct. Ensure TELEGRAM_MODE=webhook or polling is set. Check bot token is valid.',
      },
    ],
  },
  {
    category: 'Legal',
    icon: Scale,
    color: 'amber',
    items: [
      {
        q: 'Is this legal?',
        a: 'Yes — paper-trading educational tool under South African law. Not a gambling service.',
      },
      {
        q: 'Which regulator?',
        a: 'Referenced: Mpumalanga Economic Regulator.',
      },
      {
        q: 'Where are full terms?',
        a: 'See Terms of Service, Privacy Policy, and Disclaimer pages accessible from the footer.',
      },
    ],
  },
];

const colorMap: Record<string, { bg: string; border: string; text: string; accent: string }> = {
  purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', accent: 'bg-purple-500/20' },
  cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', text: 'text-cyan-400', accent: 'bg-cyan-500/20' },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', accent: 'bg-emerald-500/20' },
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', accent: 'bg-blue-500/20' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', accent: 'bg-amber-500/20' },
};

const AccordionItem: React.FC<{ q: string; a: string; color: string }> = ({ q, a, color }) => {
  const [open, setOpen] = useState(false);
  const c = colorMap[color];
  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${open ? `${c.border}` : 'border-white/8'}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-white/3 transition-colors"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold text-white/90 leading-snug">{q}</span>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className={`w-4 h-4 shrink-0 ${c.text}`} />
        </motion.div>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className={`px-4 pb-4 pt-1 text-sm text-white/65 leading-relaxed border-t border-white/5 ${c.bg}`}>
              {a}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const FAQPage: React.FC = () => {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const filtered = FAQ_SECTIONS.map(section => ({
    ...section,
    items: section.items.filter(
      item =>
        item.q.toLowerCase().includes(search.toLowerCase()) ||
        item.a.toLowerCase().includes(search.toLowerCase())
    ),
  })).filter(section =>
    (activeCategory === null || section.category === activeCategory) &&
    section.items.length > 0
  );

  return (
    <motion.div
      className="legal-page flex-1 flex flex-col min-h-0 pb-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Hero */}
      <motion.div {...fadeUp} className="mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/10 via-cyan-500/5 to-transparent p-6 md:p-8">
          <div className="relative flex items-start gap-4">
            <button
              onClick={() => window.history.back()}
              aria-label="Go back"
              className="mt-1 p-2 rounded-xl bg-white/5 hover:bg-cyan-500/10 text-white/60 hover:text-cyan-400 transition-all border border-white/10 shrink-0"
            >
              <ArrowLeft size={18} />
            </button>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-cyan-400" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">FAQ</h1>
              </div>
              <p className="text-sm text-white/60 font-medium leading-relaxed">
                Frequently Asked Questions — Strike Tips Racing Bot
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Last Updated: June 2026</span>
                <span className="text-[10px] px-2.5 py-1 bg-white/5 border border-white/10 rounded-full font-bold uppercase tracking-widest text-white/50">Version 1.0</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Search */}
      <motion.div {...fadeUp} className="mb-6">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search questions..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-xl pl-11 pr-4 py-3 text-sm font-medium text-white placeholder-white/30 focus:outline-none focus:border-cyan-500/50 focus:bg-cyan-500/5 transition-all"
          />
        </div>
      </motion.div>

      {/* Category Tabs */}
      <motion.div {...fadeUp} className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => setActiveCategory(null)}
          className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
            activeCategory === null
              ? 'bg-white/10 border-white/20 text-white'
              : 'bg-white/3 border-white/8 text-white/50 hover:border-white/20 hover:text-white/80'
          }`}
        >
          All
        </button>
        {FAQ_SECTIONS.map(section => {
          const c = colorMap[section.color];
          return (
            <button
              key={section.category}
              onClick={() => setActiveCategory(activeCategory === section.category ? null : section.category)}
              className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
                activeCategory === section.category
                  ? `${c.bg} ${c.border} ${c.text}`
                  : 'bg-white/3 border-white/8 text-white/50 hover:border-white/20 hover:text-white/80'
              }`}
            >
              {section.category}
            </button>
          );
        })}
      </motion.div>

      {/* FAQ Sections */}
      <div className="space-y-8">
        {filtered.map((section) => {
          const Icon = section.icon;
          const c = colorMap[section.color];
          return (
            <motion.div key={section.category} {...fadeUp}>
              <div className="flex items-center gap-2 mb-4">
                <div className={`w-8 h-8 rounded-lg ${c.bg} ${c.border} border flex items-center justify-center`}>
                  <Icon className={`w-4 h-4 ${c.text}`} />
                </div>
                <h2 className={`text-base font-black ${c.text}`}>{section.category}</h2>
                <span className="text-[10px] font-bold text-white/30 ml-1">({section.items.length})</span>
              </div>
              <div className="space-y-2">
                {section.items.map((item, i) => (
                  <AccordionItem key={i} q={item.q} a={item.a} color={section.color} />
                ))}
              </div>
            </motion.div>
          );
        })}

        {filtered.length === 0 && (
          <motion.div {...fadeUp} className="text-center py-16">
            <HelpCircle className="w-12 h-12 text-white/20 mx-auto mb-4" />
            <p className="text-white/40 font-medium">No questions match your search</p>
          </motion.div>
        )}
      </div>

      {/* Contact Footer */}
      <motion.div {...fadeUp} className="mt-8 p-4 rounded-xl bg-white/3 border border-white/10">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="text-sm font-bold text-white mb-1">Still have questions?</div>
            <div className="text-xs text-white/50">Contact us via Telegram or responsible gambling helpline</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="flex items-center gap-2 text-xs font-bold px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400">
              <Send className="w-3 h-3" />
              @StrikeTipsBot
            </div>
            <div className="flex items-center gap-2 text-xs font-bold px-3 py-1.5 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400">
              <Phone className="w-3 h-3" />
              0800 006 008
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
