import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { apiFetch } from '../lib/api-fetch';

const STORAGE_KEY = 'strike_chat_messages';

export const AIChat: React.FC = () => {
  const [messages, setMessages] = useState<{role: 'user' | 'ai', content: string, timestamp: string, activity?: string}[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [sessions] = useState<{id: string, title: string}[]>([
    { id: '1', title: 'Race Triage - Kelso' },
    { id: '2', title: 'Bankroll Strategy' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentActivity, setCurrentActivity] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('auto');
  const [lastModelUsed, setLastModelUsed] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const getActivities = (msg: string): string[] => {
    const m = msg.toLowerCase();
    if (m.includes('race') || m.includes('scan') || m.includes('track'))
      return ["🔍 Checking TAB4Racing schedule...", "📡 Fetching live racecards...", "🏇 Analysing runners & form..."];
    if (m.includes('odds') || m.includes('price'))
      return ["📊 Pulling OddsChecker data...", "⚖️ Comparing market prices...", "🎯 Calculating implied probabilities..."];
    if (m.includes('edge') || m.includes('value') || m.includes('prob'))
      return ["🧮 Running edge calculation...", "📐 Applying Half-Kelly formula...", "✅ Checking value threshold (>5%)..."];
    if (m.includes('bankroll') || m.includes('balance') || m.includes('account'))
      return ["💰 Fetching bankroll state...", "📈 Calculating P&L..."];
    if (m.includes('form') || m.includes('history') || m.includes('past'))
      return ["🗄️ Searching ChromaDB memory...", "📜 Retrieving past race insights...", "🔗 Cross-referencing form data..."];
    return ["🧠 Strike Brain processing...", "⚡ Routing to specialist agent...", "📡 Awaiting model response..."];
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input;
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: now }]);
    setInput('');
    setLoading(true);

    const activities = getActivities(userMsg);
    setCurrentActivity(activities[0]);
    let actIdx = 1;
    const actInterval = setInterval(() => {
      if (actIdx < activities.length) {
        setCurrentActivity(activities[actIdx]);
        actIdx++;
      } else {
        clearInterval(actInterval);
      }
    }, 2000);

    // Add empty AI message that we'll stream into
    setMessages(prev => [...prev, { role: 'ai', content: '', timestamp: now }]);

    try {
      const res = await apiFetch('/api/agent/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMsg,
          model: selectedModel !== 'auto' ? selectedModel : undefined,
        }),
      });

      const data = await res.json();
      clearInterval(actInterval);
      setCurrentActivity(null);

      const text = data.response || data.summary || 'No response received.';
      const modelUsed = data.model || data.model_used || '';
      if (modelUsed) setLastModelUsed(modelUsed);

      setMessages(prev => prev.map((m, i) =>
        i === prev.length - 1 && m.role === 'ai'
          ? { ...m, content: text, activity: modelUsed }
          : m
      ));
    } catch {
      clearInterval(actInterval);
      setMessages(prev => prev.map((m, i) =>
        i === prev.length - 1 && m.role === 'ai'
          ? { ...m, content: 'Error connecting to brain.' }
          : m
      ));
    } finally {
      clearInterval(actInterval);
      setLoading(false);
      setCurrentActivity(null);
    }
  };

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, currentActivity]);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-50))); } catch {}
  }, [messages]);

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex h-full min-h-[450px] md:min-h-[500px] bg-white/5 border border-white/10 rounded-3xl overflow-hidden backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] w-full"
    >
      {/* Session Sidebar — Hidden on mobile */}
      <div className="hidden md:flex w-44 border-r border-white/10 p-4 bg-black/20 flex-col gap-2 shrink-0">
        <div className="text-[9px] font-black uppercase text-purple-500 mb-2 tracking-widest">Sessions</div>
        {sessions.map(s => (
          <button key={s.id} className="text-[10px] text-left text-slate-400 hover:text-white hover:bg-white/5 p-2 rounded-lg truncate transition-all">
            {s.title}
          </button>
        ))}
        <div className="mt-auto flex flex-col gap-2 pt-4 border-t border-white/10">
          <button className="text-[10px] font-bold text-slate-600 hover:text-purple-400">Export Logs</button>
          <button onClick={() => { setMessages([]); localStorage.removeItem(STORAGE_KEY); }} className="text-[10px] font-bold text-red-500/60 hover:text-red-500">Clear Session</button>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="p-3 md:p-4 border-b border-white/10 bg-white/5 flex items-center justify-between gap-2 overflow-hidden">
            <div className="flex items-center gap-2 md:gap-3 shrink-0">
              <Bot className="w-4 h-4 md:w-5 md:h-5 text-purple-400" />
              <span className="text-[9px] md:text-[10px] font-black uppercase tracking-widest text-white truncate">Strike Command</span>
            </div>
            {currentActivity && (
                <div className="px-2.5 py-0.5 md:py-1 bg-purple-500/10 border border-purple-500/30 rounded-full flex items-center gap-1.5 animate-pulse min-w-0">
                    <Loader2 className="w-2.5 h-2.5 text-purple-400 animate-spin shrink-0" />
                    <span className="text-[8px] md:text-[9px] font-bold text-purple-300 uppercase truncate">{currentActivity}</span>
                </div>
            )}
            <div className="flex gap-1.5 items-center shrink-0">
              <div className="px-1.5 md:px-2 py-0.5 bg-purple-900/30 border border-purple-500/50 rounded text-[8px] md:text-[9px] font-bold text-purple-300 uppercase">
                {currentActivity ? 'RUNNING' : 'ACTIVE'}
              </div>
              {lastModelUsed && (
                <div className="hidden sm:block px-1.5 md:px-2 py-0.5 bg-emerald-900/30 border border-emerald-500/40 rounded text-[8px] md:text-[9px] font-bold text-emerald-300 uppercase">
                  {lastModelUsed}
                </div>
              )}
            </div>
        </div>
        
        <div ref={scrollRef} className="flex-1 p-4 md:p-6 overflow-y-auto space-y-4 md:space-y-6 font-mono text-[11px] md:text-xs custom-scrollbar">
            {messages.length === 0 && (
                <div className="text-center text-slate-600 mt-20 italic text-[10px] uppercase tracking-wider">
                    Awaiting parameters...
                </div>
            )}
            {messages.map((m, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              key={i} 
              className={`flex flex-col gap-1 ${m.role === 'user' ? 'items-end' : ''}`}
            >
                <div className="text-[7px] md:text-[8px] text-slate-600 uppercase px-1">{m.timestamp}</div>
                <div className={`flex gap-2 md:gap-3 ${m.role === 'user' ? 'justify-end' : ''} w-full`}>
                    {m.role === 'ai' && <Bot className="w-4 h-4 md:w-5 md:h-5 text-purple-500 shrink-0 mt-1" />}
                    <div className={`p-3 md:p-4 rounded-2xl max-w-[88%] md:max-w-[78%] break-words ${m.role === 'user' ? 'bg-purple-600/90 text-white shadow-[0_0_15px_rgba(168,85,247,0.2)] ml-auto' : 'bg-white/5 text-slate-350 border border-white/10 shadow-[0_0_15px_rgba(0,0,0,0.15)] mr-auto'}`}>
                      {m.content}
                    </div>
                    {m.role === 'user' && <User className="w-4 h-4 md:w-5 md:h-5 text-slate-500 shrink-0 mt-1" />}
                </div>
            </motion.div>
            ))}
            {loading && (
              <div className="flex gap-2 md:gap-3">
                <Bot className="w-4 h-4 md:w-5 md:h-5 text-purple-500 animate-pulse" />
                <Loader2 className="w-4 h-4 md:w-5 md:h-5 animate-spin text-purple-500" />
              </div>
            )}
        </div>

        <div className="p-3 md:p-4 border-t border-white/10 bg-black/40 flex flex-col sm:flex-row gap-2.5">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-theme-panel border border-white/10 rounded-xl px-3 py-2.5 text-white text-[11px] font-bold focus:outline-none focus:border-purple-500 w-full sm:w-auto"
            >
              <option value="auto" className="bg-black">⚡ Auto Router</option>
              <option value="groq:llama-3.1-8b-instant" className="bg-black">Groq Llama 3.1 8B (Fast)</option>
              <option value="groq:llama-3.3-70b-versatile" className="bg-black">Groq Llama 3.3 70B (Tools)</option>
              <option value="gemini:gemini-2.5-flash-lite" className="bg-black">Gemini Flash Lite</option>
              <option value="gemini:gemini-2.5-flash" className="bg-black">Gemini Flash</option>
              <option value="gemini:gemini-2.5-pro" className="bg-black">Gemini Pro</option>
            </select>
            <div className="flex gap-2 flex-1 w-full min-w-0">
              <input 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Type command..."
                className="flex-1 bg-transparent border border-white/10 rounded-xl px-3.5 py-2.5 text-white text-xs placeholder-slate-600 focus:outline-none focus:border-purple-500 focus:bg-white/5 transition-colors min-w-0"
              />
              <button 
                onClick={sendMessage} 
                className="bg-purple-600 px-5 rounded-xl hover:bg-purple-500 transition-all font-black uppercase text-[10px] tracking-wider shadow-[0_0_15px_rgba(168,85,247,0.3)] shrink-0"
              >
                Send
              </button>
            </div>
        </div>
      </div>
    </motion.div>
  );
};
