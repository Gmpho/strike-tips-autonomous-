import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

export const AIChat: React.FC = () => {
  const [messages, setMessages] = useState<{role: 'user' | 'ai', content: string, timestamp: string, activity?: string}[]>([]);
  const [sessions] = useState<{id: string, title: string}[]>([
    { id: '1', title: 'Race Triage - Kelso' },
    { id: '2', title: 'Bankroll Strategy' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentActivity, setCurrentActivity] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('auto');
  const [lastModelUsed] = useState<string | null>(null);
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
    let actIdx = 0;
    setCurrentActivity(activities[0]);
    const actInterval = setInterval(() => {
      actIdx = (actIdx + 1) % activities.length;
      setCurrentActivity(activities[actIdx]);
    }, 2000);

    // Add empty AI message that we'll stream into
    setMessages(prev => [...prev, { role: 'ai', content: '', timestamp: now }]);

    try {
      const res = await fetch('/ollama/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel !== 'auto' ? selectedModel : 'racing_llama',
          messages: [{ role: 'user', content: userMsg }],
          stream: true,
        }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const chunk = JSON.parse(line);
            if (chunk.message && chunk.message.content) {
              clearInterval(actInterval);
              setCurrentActivity(null);
              setMessages(prev => prev.map((m, i) =>
                i === prev.length - 1 && m.role === 'ai'
                  ? { ...m, content: m.content + chunk.message.content }
                  : m
              ));
            }
          } catch (e) { console.error('Stream parse error', e); }
        }
      }
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

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex h-full min-h-[400px] bg-white/5 border border-white/10 rounded-3xl overflow-hidden backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
    >
      {/* Session Sidebar */}
      <div className="w-48 border-r border-white/10 p-4 bg-black/20 flex flex-col gap-2">
        <div className="text-[9px] font-black uppercase text-purple-500 mb-2 tracking-widest">Sessions</div>
        {sessions.map(s => (
          <button key={s.id} className="text-[10px] text-left text-slate-400 hover:text-white hover:bg-white/5 p-2 rounded-lg truncate transition-all">
            {s.title}
          </button>
        ))}
        <div className="mt-auto flex flex-col gap-2 pt-4 border-t border-white/10">
          <button className="text-[10px] font-bold text-slate-600 hover:text-purple-400">Export Logs</button>
          <button onClick={() => setMessages([])} className="text-[10px] font-bold text-red-500/60 hover:text-red-500">Clear Session</button>
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b border-white/10 bg-white/5 flex items-center justify-between">
            <div className="flex items-center gap-3">
            <Bot className="w-5 h-5 text-purple-400" />
            <span className="text-[10px] font-black uppercase tracking-widest text-white">Strike Brain Command</span>
            </div>
            {currentActivity && (
                <div className="px-3 py-1 bg-purple-500/10 border border-purple-500/30 rounded-full flex items-center gap-2 animate-pulse">
                    <Loader2 className="w-3 h-3 text-purple-400 animate-spin" />
                    <span className="text-[9px] font-bold text-purple-300 uppercase">{currentActivity}</span>
                </div>
            )}
            <div className="px-2 py-0.5 bg-purple-900/30 border border-purple-500/50 rounded text-[9px] font-bold text-purple-300 uppercase">
              {currentActivity ? 'PROCESSING' : 'SYSTEM_READY'}
            </div>
            {lastModelUsed && (
              <div className="px-2 py-0.5 bg-emerald-900/30 border border-emerald-500/40 rounded text-[9px] font-bold text-emerald-300 uppercase">
                {lastModelUsed}
              </div>
            )}
        </div>
        
        <div ref={scrollRef} className="flex-1 p-6 overflow-y-auto space-y-6 font-mono text-xs custom-scrollbar">
            {messages.length === 0 && (
                <div className="text-center text-slate-600 mt-20 italic">
                    Awaiting mission parameters...
                </div>
            )}
            {messages.map((m, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              key={i} 
              className={`flex flex-col gap-1 ${m.role === 'user' ? 'items-end' : ''}`}
            >
                <div className="text-[8px] text-slate-600 uppercase px-1">{m.timestamp}</div>
                <div className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
                    {m.role === 'ai' && <Bot className="w-5 h-5 text-purple-500 shrink-0" />}
                    <div className={`p-4 rounded-2xl max-w-[85%] ${m.role === 'user' ? 'bg-purple-600/90 text-white shadow-[0_0_15px_rgba(168,85,247,0.3)]' : 'bg-white/5 text-slate-300 border border-white/10 shadow-[0_0_15px_rgba(0,0,0,0.2)]'}`}>
                    {m.content}
                    </div>
                    {m.role === 'user' && <User className="w-5 h-5 text-slate-500 shrink-0" />}
                </div>
            </motion.div>
            ))}
            {loading && <div className="flex gap-3"><Bot className="w-5 h-5 text-purple-500 animate-pulse" /><Loader2 className="w-5 h-5 animate-spin text-purple-500" /></div>}
        </div>

        <div className="p-4 border-t border-white/10 bg-black/40 flex gap-3">
            <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="bg-transparent border border-white/10 rounded-xl px-3 py-3 text-white text-xs focus:outline-none focus:border-purple-500"
            >
            <option value="auto" className="bg-black">Auto Route</option>
            <option value="racing_llama" className="bg-black">racing_llama</option>
            <option value="racing_qwen" className="bg-black">racing_qwen</option>
            <option value="func_gemma" className="bg-black">func_gemma</option>
            <option value="lfm_racing" className="bg-black">lfm_racing</option>
            <option value="ds_racing" className="bg-black">ds_racing</option>
            </select>
            <input 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Execute tactical commands..."
            className="flex-1 bg-transparent border border-white/10 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-600 focus:outline-none focus:border-purple-500 focus:bg-white/5 transition-colors"
            />
            <button onClick={sendMessage} className="bg-purple-600 px-6 rounded-xl hover:bg-purple-500 transition-all font-black uppercase text-[10px] shadow-[0_0_15px_rgba(168,85,247,0.4)]">
            Send
            </button>
        </div>
      </div>
    </motion.div>
  );
};
