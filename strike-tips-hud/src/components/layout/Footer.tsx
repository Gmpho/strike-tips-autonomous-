import React from 'react';
import { ShieldCheck, Info, FileText, Lock, LifeBuoy, MessageSquare, FileText as FileTextIcon } from 'lucide-react';

export const Footer: React.FC = () => {
  const links = [
    { label: 'How To Bet', icon: Info, href: '/how-to-bet' },
    { label: 'FAQ', icon: MessageSquare, href: '/faq' },
    { label: 'Betting Rules', icon: FileText, href: '/betting-rules' },
    { label: 'T&Cs', icon: ShieldCheck, href: '/terms' },
    { label: 'Privacy', icon: Lock, href: '/privacy' },
    { label: 'Disclaimer', icon: FileTextIcon, href: '/disclaimer' },
    { label: 'Responsible', icon: LifeBuoy, href: '/responsible' },
    { label: 'Contact', icon: MessageSquare, href: '/contact' },
  ];

  return (
    <footer className="px-4 md:px-8 lg:px-12 py-4 md:py-8 border-t border-theme bg-theme-panel backdrop-blur-xl">
      <div className="max-w-7xl mx-auto">
        {/* Links */}
        <div className="flex flex-wrap justify-center gap-2 md:gap-4 lg:gap-8 mb-4 md:mb-8">
          {links.map((link, idx) => (
            <a
              key={idx}
              href={link.href}
              className="flex items-center gap-1.5 md:gap-2 group transition-all"
              target={link.href.startsWith('/') ? undefined : '_blank'}
              rel={link.href.startsWith('/') ? undefined : 'noopener noreferrer'}
            >
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-lg bg-theme-secondary flex items-center justify-center group-hover:bg-purple-500/20 group-hover:text-purple-400 transition-colors border border-theme group-hover:border-purple-500/30">
                <link.icon className="w-3 h-3 md:w-4 md:h-4 opacity-60 group-hover:opacity-100" />
              </div>
              <span className="text-[8px] md:text-[10px] font-black text-theme-secondary uppercase tracking-tighter group-hover:text-theme-primary transition-colors">
                {link.label}
              </span>
            </a>
          ))}
        </div>

        {/* Legal */}
        <div className="bg-theme-secondary border border-theme rounded-xl md:rounded-2xl p-3 md:p-6 mb-4 md:mb-6">
          <div className="flex flex-col md:flex-row gap-3 md:gap-6 items-center">
            <div className="w-8 h-8 md:w-12 md:h-12 rounded-full bg-rose-500/20 border border-rose-500/30 flex items-center justify-center shrink-0">
              <span className="text-[10px] md:text-sm font-black text-rose-500">18+</span>
            </div>
            <div className="flex-1 text-center md:text-left">
              <p className="text-[8px] md:text-[10px] leading-relaxed text-theme-secondary font-bold uppercase tracking-tight">
                No persons under the age of 18 are permitted to bet. Winners know when to stop.
                <span className="text-rose-400/80 mx-1">National Responsible Gambling Programme:</span>
                0800 006 008 or WHATSAPP 'HELP' to 076 675 0710.
              </p>
              <p className="text-[7px] md:text-[9px] leading-relaxed text-theme-secondary font-medium mt-1">
                Warning: Gambling involves risk. All games are fixed-odds betting events.
              </p>
            </div>
            <div className="shrink-0">
              <div className="px-2 md:px-3 py-0.5 md:py-1 bg-emerald-500/5 border border-emerald-500/10 rounded-md">
                <span className="text-[7px] md:text-[9px] font-black text-emerald-400/70 uppercase tracking-widest">MPUMALANGA ECONOMIC REGULATOR</span>
              </div>
            </div>
          </div>
        </div>

        {/* Copyright */}
        <div className="flex justify-between items-center opacity-60 px-2">
          <span className="text-[7px] md:text-[9px] font-black uppercase tracking-[0.3em]">STRIKE TIPS INTELLIGENCE</span>
          <span className="text-[7px] md:text-[9px] font-black uppercase tracking-widest">&copy; 2026 STRIKE</span>
        </div>
      </div>
    </footer>
  );
};
