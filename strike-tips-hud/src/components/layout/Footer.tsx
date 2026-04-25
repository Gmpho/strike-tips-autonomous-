import React from 'react';
import { ShieldCheck, Info, LifeBuoy, FileText, Lock, MessageSquare } from 'lucide-react';

export const Footer: React.FC = () => {
  const links = [
    { label: 'How To Bet', icon: Info },
    { label: 'FAQ', icon: MessageSquare },
    { label: 'Betting Rules', icon: FileText },
    { label: 'T&Cs', icon: ShieldCheck },
    { label: 'Privacy', icon: Lock },
    { label: 'Responsible', icon: LifeBuoy },
    { label: 'Contact', icon: MessageSquare },
  ];

  return (
    <footer className="mt-8 py-8 border-t border-theme bg-theme-panel backdrop-blur-xl px-8 rounded-t-4xl">
      <div className="max-w-7xl mx-auto">
        {/* Links Grid - Compact */}
        <div className="flex flex-wrap justify-center gap-4 md:gap-8 mb-8">
          {links.map((link, idx) => (
            <a 
              key={idx} 
              href="#" 
              className="flex items-center gap-2 group transition-all"
            >
              <div className="w-8 h-8 rounded-lg bg-theme-secondary flex items-center justify-center group-hover:bg-purple-500/20 group-hover:text-purple-400 transition-colors border border-theme group-hover:border-purple-500/30">
                <link.icon className="w-4 h-4 opacity-60 group-hover:opacity-100" />
              </div>
              <span className="text-[10px] font-black text-theme-secondary uppercase tracking-tighter group-hover:text-theme-primary transition-colors">
                {link.label}
              </span>
            </a>
          ))}
        </div>

        {/* Legal - More Compact */}
        <div className="bg-theme-secondary border border-theme rounded-2xl p-6 mb-6">
          <div className="flex flex-col lg:flex-row gap-6 items-center">
            <div className="w-12 h-12 rounded-full bg-rose-500/20 border border-rose-500/30 flex items-center justify-center shrink-0">
              <span className="text-sm font-black text-rose-500">18+</span>
            </div>
            
            <div className="flex-1 text-center lg:text-left">
              <p className="text-[10px] leading-relaxed text-theme-secondary font-bold uppercase tracking-tight">
                No persons under the age of 18 are permitted to bet. Winners know when to stop. 
                <span className="text-rose-400/80 mx-1">National Responsible Gambling Programme:</span> 
                0800 006 008 or WHATSAPP 'HELP' to 076 675 0710.
              </p>
              <p className="text-[9px] leading-relaxed text-theme-secondary opacity-60 font-medium mt-1">
                Warning: Gambling involves risk. All games are fixed-odds betting events.
              </p>
            </div>

            <div className="shrink-0">
              <div className="px-3 py-1 bg-emerald-500/5 border border-emerald-500/10 rounded-md">
                <span className="text-[9px] font-black text-emerald-500/60 uppercase tracking-widest">MPUMALANGA ECONOMIC REGULATOR</span>
              </div>
            </div>
          </div>
        </div>

        {/* Copyright */}
        <div className="flex justify-between items-center opacity-30 px-2">
          <span className="text-[9px] font-black uppercase tracking-[0.3em]">STRIKE TIPS INTELLIGENCE</span>
          <span className="text-[9px] font-black uppercase tracking-widest">&copy; 2026 STRIKE</span>
        </div>
      </div>
    </footer>
  );
};
