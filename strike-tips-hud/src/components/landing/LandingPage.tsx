import React from 'react';
import { TrendingUp, Globe2, Fingerprint, BellRing, Wallet, TableProperties } from 'lucide-react';
import { GoogleLoginButton } from './GoogleLoginButton';

const NAV = [
  { label: 'Home', href: '#home' },
  { label: 'Story', href: '#story' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Learn More', href: '#learn' },
];

const CARDS = [
  {
    icon: TrendingUp,
    title: 'Value-Bet Engine',
    body: 'Every runner priced against the live market. Only edges above the threshold get flagged — silence means no value, not a broken scanner.',
  },
  {
    icon: Globe2,
    title: 'SA Track Coverage',
    body: 'Vaal, Turffontein, Greyville, Kenilworth, Durbanville and Fairview — full cards, exotics, market movers and results.',
  },
  {
    icon: BellRing,
    title: 'Telegram + Bankroll',
    body: 'Instant value alerts on your phone, passcode-linked to your account, with every cent governed by Kelly staking.',
  },
];

const scrollTo = (e: React.MouseEvent, href: string) => {
  e.preventDefault();
  document.querySelector(href)?.scrollIntoView({ behavior: 'smooth' });
};

export const LandingPage: React.FC = () => {
  return (
    <div id="home" className="min-h-screen bg-[#121016] text-white antialiased">
      {/* Nav */}
      <header className="max-w-6xl mx-auto flex items-center gap-8 px-6 py-5">
        <div className="flex items-center gap-2 font-black tracking-widest text-sm">
          <span className="text-2xl">🏇</span> STRIKE&nbsp;TIPS
        </div>
        <nav className="hidden md:flex items-center gap-7 text-sm text-white/80">
          {NAV.map((n) => (
            <a key={n.label} href={n.href} onClick={(e) => scrollTo(e, n.href)} className="hover:text-white transition-colors">
              {n.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-6">
          <a href="#about" onClick={(e) => scrollTo(e, '#about')} className="hidden md:inline text-sm text-white/80 hover:text-white transition-colors">
            About
          </a>
          <a
            href="#login"
            onClick={(e) => scrollTo(e, '#login')}
            className="text-sm font-semibold px-5 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 transition-all"
          >
            Sign In
          </a>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-10 pb-16 grid md:grid-cols-2 gap-10 items-center">
        <div>
          <h1 className="text-5xl md:text-6xl font-black leading-tight">
            Horse Racing<br />Intelligence
          </h1>
          <p className="mt-5 text-lg text-white/75 max-w-md">
            Real-time value detection and bankroll discipline for South African horse racing.
          </p>
          <div id="login" className="mt-8 flex flex-wrap items-center gap-4">
            <a
              href="#login"
              onClick={(e) => scrollTo(e, '#login')}
              className="px-7 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold transition-all"
            >
              Get Started
            </a>
            <GoogleLoginButton />
          </div>
          <p className="mt-4 text-xs text-white/40">Free while in beta · Google sign-in · No card required</p>
        </div>
        {/* Chart motif — pure CSS/SVG, no external image */}
        <div className="relative hidden md:block rounded-2xl bg-white/[0.03] border border-white/10 p-8 overflow-hidden">
          <svg viewBox="0 0 400 220" className="w-full h-auto" aria-hidden="true">
            <polyline
              points="10,190 60,175 100,182 150,140 200,150 250,100 300,110 350,40 390,25"
              fill="none" stroke="#3b82f6" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"
            />
            <polygon points="350,40 390,25 378,48" fill="#3b82f6" />
            <text x="18" y="205" fill="rgba(255,255,255,0.35)" fontSize="11">VAAL</text>
            <text x="150" y="205" fill="rgba(255,255,255,0.35)" fontSize="11">TURFFONTEIN</text>
            <text x="255" y="205" fill="rgba(255,255,255,0.35)" fontSize="11">GREYVILLE</text>
          </svg>
          <div className="mt-4 flex items-center gap-3 text-sm">
            <span className="text-4xl">🏇</span>
            <div>
              <p className="font-bold">Bankroll R3,799.56 <span className="text-emerald-400 text-xs font-black">PEAK</span></p>
              <p className="text-white/50 text-xs">Lifetime P&L +R2,799.56 · 33.8% win rate</p>
            </div>
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section className="max-w-6xl mx-auto px-6 pb-20 grid md:grid-cols-3 gap-5">
        {CARDS.map((c) => (
          <div key={c.title} className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">{c.title}</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">{c.body}</p>
            <c.icon className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
        ))}
      </section>

      {/* Story */}
      <section id="story" className="max-w-6xl mx-auto px-6 pb-20">
        <h2 className="text-3xl font-black">Story</h2>
        <p className="mt-4 max-w-2xl text-white/70 leading-relaxed">
          Strike Tips was born from a months-long bug hunt: the bot parroted the race card on every
          message instead of answering the question. Fixing that forced real intent routing, real
          grounding, and real discipline — a snapshot only when the turn is about racing, web search
          when asked, tables you can read on your phone. The pundit you talk to at 2am, not a
          corporate drone.
        </p>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-6 pb-20">
        <h2 className="text-3xl font-black">Pricing</h2>
        <div className="mt-6 max-w-md rounded-2xl bg-white/[0.04] border border-white/10 p-7">
          <p className="text-xl font-bold">Beta — Free</p>
          <p className="mt-2 text-sm text-white/65">Full scanner, Telegram alerts, bankroll governor. No card, no catch — you're helping train the future pricing.</p>
        </div>
      </section>

      {/* Learn More / About */}
      <section id="learn" className="max-w-6xl mx-auto px-6 pb-10">
        <h2 className="text-3xl font-black">Learn More</h2>
        <div className="mt-4 grid md:grid-cols-3 gap-5 text-sm text-white/65">
          <div className="flex gap-3"><Wallet className="w-5 h-5 shrink-0 text-white/80" /><p><b className="text-white">Bankroll discipline.</b> Half-Kelly stakes, 5% max exposure, daily loss limits. The governor can say no — that's the feature.</p></div>
          <div className="flex gap-3"><TableProperties className="w-5 h-5 shrink-0 text-white/80" /><p><b className="text-white">Your ledger, queryable.</b> Every bet, settlement and snapshot stored per user — no more grepping JSON files.</p></div>
          <div className="flex gap-3"><Fingerprint className="w-5 h-5 shrink-0 text-white/80" /><p><b className="text-white">Your account, isolated.</b> Google sign-in with row-level security — your bets are invisible to everyone else.</p></div>
        </div>
      </section>

      <footer id="about" className="border-t border-white/10 mt-10">
        <div className="max-w-6xl mx-auto px-6 py-8 text-xs text-white/40 flex flex-wrap gap-x-8 gap-y-2">
          <span className="font-black tracking-widest text-white/60">🏇 STRIKE TIPS</span>
          <span>South African horse racing intelligence.</span>
          <span className="ml-auto">Play responsibly. Winnings not guaranteed.</span>
        </div>
      </footer>
    </div>
  );
};
