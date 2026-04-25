import React from 'react';
import { ShieldCheck, Info, LifeBuoy, FileText, Lock, MessageSquare } from 'lucide-react';

export const Footer: React.FC = () => {
  const links = [
    { label: 'How To Bet', icon: Info },
    { label: 'Frequently asked questions', icon: MessageSquare },
    { label: 'Betting Rules', icon: FileText },
    { label: 'Terms & Conditions', icon: ShieldCheck },
    { label: 'Privacy Policy', icon: Lock },
    { label: 'Responsible Gambling', icon: LifeBuoy },
    { label: 'Contact Us', icon: MessageSquare },
  ];

  return (
    <footer className="mt-12 pt-12 border-t border-white/5 bg-black/40 backdrop-blur-3xl px-8 pb-12 rounded-t-[3rem]">
      <div className="max-w-7xl mx-auto">
        {/* Links Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-6 mb-12">
          {links.map((link, idx) => (
            <a 
              key={idx} 
              href="#" 
              className="flex flex-col items-center gap-2 group transition-all"
            >
              <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center group-hover:bg-purple-500/20 group-hover:text-purple-400 transition-colors border border-white/5 group-hover:border-purple-500/30">
                <link.icon className="w-5 h-5 opacity-60 group-hover:opacity-100" />
              </div>
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter text-center group-hover:text-white transition-colors leading-tight">
                {link.label}
              </span>
            </a>
          ))}
        </div>

        {/* Legal & Responsible Gambling */}
        <div className="bg-white/5 border border-white/10 rounded-3xl p-8 lg:p-10 mb-8">
          <div className="flex flex-col lg:flex-row gap-8 items-start lg:items-center">
            <div className="w-20 h-20 rounded-full bg-rose-500/20 border border-rose-500/30 flex items-center justify-center shrink-0">
              <span className="text-2xl font-black text-rose-500">18+</span>
            </div>
            
            <div className="flex-1">
              <p className="text-[11px] leading-relaxed text-slate-400 font-bold uppercase tracking-wide">
                No persons under the age of 18 years are permitted to bet. Winners know when to stop. 
                <span className="text-rose-400 mx-1">National Responsible Gambling Programme:</span> 
                <span className="text-white">0800 006 008</span> or WHATSAPP 'HELP' to 
                <span className="text-white">076 675 0710</span> (South Africa Responsible Gambling Foundation).
              </p>
              <div className="h-px bg-white/10 my-4" />
              <p className="text-[10px] leading-relaxed text-slate-500 font-medium">
                <span className="text-amber-500/80 font-black uppercase tracking-widest mr-2">Warning:</span>
                Gambling involves risk, bet responsibly. Gambling on this website, you run the risk that you may lose. All games are fixed-odds betting events.
              </p>
            </div>

            <div className="shrink-0 flex flex-col items-center gap-2">
              <div className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">MPUMALANGA ECONOMIC REGULATOR</span>
              </div>
            </div>
          </div>
        </div>

        {/* Copyright */}
        <div className="flex justify-between items-center px-4">
          <div className="flex flex-col">
            <span className="text-[10px] font-black text-slate-700 uppercase tracking-[0.4em]">STRIKE TIPS INTELLIGENCE</span>
            <span className="text-[9px] text-slate-800 uppercase font-bold mt-1">Regulated Gaming Framework v7.2</span>
          </div>
          <div className="text-[10px] font-black text-slate-700 uppercase tracking-[0.2em]">
            &copy; 2026 STRIKE. ALL RIGHTS RESERVED.
          </div>
        </div>
      </div>
    </footer>
  );
};
