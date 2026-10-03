import React from 'react';
import { TrendingUp, Globe2, Fingerprint, BellRing, Wallet, TableProperties, BookOpen, Tag, Sparkles } from 'lucide-react';
import { GoogleLoginButton } from './GoogleLoginButton';
import { ThemeToggle } from '../ThemeToggle';

const NAV = [
  { label: 'Home', href: '/' },
  { label: 'Story', href: '#story' },
  { label: 'Learn More', href: '#learn' },
];

const CARDS = [
  {
    icon: TrendingUp,
    title: 'Value-Bet Engine',
    body: 'Every runner measured against the live market. Only genuine value gets flagged — when it goes quiet, the prices are right, not broken.',
  },
  {
    icon: Globe2,
    title: 'SA Track Coverage',
    body: 'Home ground South Africa — Vaal, Turffontein, Greyville, Kenilworth and more — with predictors and market movers scanning worldwide. International race scans landing soon.',
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
    <div id="home" className="landing-root min-h-screen bg-[#121016] text-white antialiased">
      {/* Nav — sticky glass */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-[#121016]/80 border-b border-white/10">
        <div className="max-w-6xl mx-auto flex items-center gap-8 px-6 py-4">
        <a href="/" className="flex items-center gap-2 font-black tracking-widest text-sm">
          <span className="text-2xl">🏇</span> STRIKE&nbsp;TIPS
        </a>
        <nav className="hidden md:flex items-center gap-7 text-sm text-white/80">
          <a href="/" className="nav-glow hover:text-white transition-colors">Home</a>
          {NAV.slice(1).map((n) => (
            <a key={n.label} href={n.href} onClick={(e) => scrollTo(e, n.href)} className="nav-glow hover:text-white transition-colors">
              {n.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <a href="#about" onClick={(e) => scrollTo(e, '#about')} className="nav-glow hidden md:inline text-sm text-white/80 hover:text-white transition-colors">
            About
          </a>
          <a href="/support" className="nav-glow hidden md:inline text-sm text-white/80 hover:text-white transition-colors">
            Support
          </a>
          <ThemeToggle />
          <GoogleLoginButton compact />
        </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-10 pb-16 grid md:grid-cols-2 gap-10 items-center">
        <div>
          <h1 className="text-5xl md:text-6xl font-black leading-tight">
            Horse Racing<br />Intelligence
          </h1>
          <p className="mt-5 text-lg text-white/75 max-w-md">
            Rooted in South African racing, covering tracks worldwide — real-time value detection and bankroll discipline, from Vaal to the world.
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
        {/* Hero visual: compressed WebP set (57KB@1200w). Explicit size = no CLS.
            Glassglow frame: purple glow ring + gradient edge. */}
        <div className="relative hidden md:block rounded-3xl p-[1.5px] bg-gradient-to-br from-purple-500/60 via-white/10 to-indigo-500/60 shadow-[0_0_60px_-10px_rgba(168,85,247,0.5)]">
          <div className="rounded-3xl overflow-hidden">
          <img
            src="/assets/hero-race-1200.webp"
            srcSet="/assets/hero-race-800.webp 800w, /assets/hero-race-1200.webp 1200w"
            sizes="(max-width: 768px) 100vw, 50vw"
            width={1200}
            height={800}
            alt="Two racehorses battling to the finish line under their jockeys"
            fetchPriority="high"
            decoding="async"
            className="w-full h-auto object-cover"
          />
          </div>
          {/* Glass bankroll strip floating over the image */}
          <div className="absolute bottom-4 inset-x-4 rounded-2xl border border-white/20 bg-white/10 backdrop-blur-xl px-5 py-3.5 flex items-center gap-3 text-sm shadow-[0_8px_30px_rgba(0,0,0,0.45)]">
            <span className="text-3xl">🏇</span>
            <div>
              <p className="font-bold">Bankroll R3,799.56 <span className="text-emerald-400 text-xs font-black">PEAK</span></p>
              <p className="text-white/70 text-xs">Lifetime P&L +R2,799.56 · 33.8% win rate</p>
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

      {/* Story — card trio */}
      <section id="story" className="max-w-6xl mx-auto px-6 pb-20">
        <h2 className="text-3xl font-black">Story</h2>
        <p className="mt-3 max-w-2xl text-white/65 text-sm">Born from a months-long bug hunt — raised on discipline.</p>
        <div className="mt-6 grid md:grid-cols-3 gap-5">
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">The Bug</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">The bot parroted the race card on every message instead of answering the question. Months of hunting, one root cause: no intent, no grounding, no discipline.</p>
            <BookOpen className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">The Fix</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">Real intent routing, real grounding, real tables. A snapshot only when the turn is about racing, web search when asked — readable on your phone at 2am.</p>
            <Sparkles className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">The Rule</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">Never hype a horse — <em>call the price, not the dream.</em> Value edges and Kelly stakes only, enforced by a governor that can say no.</p>
            <BellRing className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
        </div>
      </section>

      {/* Pricing — card */}
      <section id="pricing" className="max-w-6xl mx-auto px-6 pb-20">
        <h2 className="text-3xl font-black">Pricing</h2>
        <div className="mt-6 grid md:grid-cols-3 gap-5">
          <div className="rounded-2xl bg-gradient-to-br from-purple-500/15 to-indigo-500/10 border border-purple-500/30 p-7 md:col-span-1">
            <p className="text-xl font-bold">Beta — Free</p>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">Full scanner, Telegram alerts, bankroll governor. No card, no catch — you're helping train the future pricing.</p>
            <Tag className="mt-6 w-9 h-9 text-purple-300" strokeWidth={1.5} />
          </div>
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7 md:col-span-2 flex flex-col justify-center">
            <p className="text-sm text-white/65 leading-relaxed">Punters in beta shape what paid tiers become. Lock in early, keep your history — your ledger carries over, nothing you've built disappears.</p>
            <div className="mt-5"><GoogleLoginButton /></div>
          </div>
        </div>
      </section>

      {/* Learn More — cards */}
      <section id="learn" className="max-w-6xl mx-auto px-6 pb-10">
        <h2 className="text-3xl font-black">Learn More</h2>
        <div className="mt-6 grid md:grid-cols-3 gap-5">
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">Bankroll discipline</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">Stakes sized to the value, losses capped daily — <em>the governor can say no, and that's the whole point.</em></p>
            <Wallet className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">Every cent accounted for</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">Every bet, every payout, every balance — tracked per punter, down to the rand.</p>
            <TableProperties className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
          <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-7">
            <h3 className="text-xl font-bold">Yours and yours alone</h3>
            <p className="mt-3 text-sm text-white/65 leading-relaxed">Sign in with Google and only you see your bets. Nobody else's, ever.</p>
            <Fingerprint className="mt-6 w-9 h-9 text-white/80" strokeWidth={1.5} />
          </div>
        </div>
      </section>

      <footer id="about" className="border-t border-white/10 mt-10">
        <div className="max-w-6xl mx-auto px-6 py-8 text-xs text-white/40 flex flex-wrap gap-x-8 gap-y-2">
          <span className="font-black tracking-widest text-white/60">🏇 STRIKE TIPS</span>
          <span>South African horse racing intelligence.</span>
          <a href="#pricing" onClick={(e) => scrollTo(e, '#pricing')} className="hover:text-white/70 transition-colors">Pricing</a>
          <a href="/support" className="hover:text-white/70 transition-colors">Support</a>
          <span className="ml-auto">Play responsibly. Winnings not guaranteed.</span>
        </div>
      </footer>
    </div>
  );
};
