import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { apiFetch } from '../lib/api-fetch';
import { checkWebGPUSupport, getWebLLMEngine } from '../lib/webllm';

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
  const [webGpuSupported, setWebGpuSupported] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkWebGPUSupport().then(supported => {
      setWebGpuSupported(supported);
    });
  }, []);

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

    if (selectedModel.startsWith('webllm-')) {
      try {
        // Fetch config to hydrate system prompt context
        let balanceInfo = '1000';
        let tracksList = 'None';
        try {
          const configRes = await apiFetch('/api/config');
          if (configRes.ok) {
            const config = await configRes.json();
            balanceInfo = config.bankroll?.total_bankroll?.toString() || '1000';
            tracksList = config.tracks?.join(', ') || 'None';
          }
        } catch (e) {
          console.warn('[WebLLM Context Fetch Failed]', e);
        }

        const systemPrompt = `You are Strike Tips Racing AI, a helpful, private on-device assistant. Answer concisely and accurately.
Today's Balance: R${balanceInfo}.
Active tracks today: ${tracksList}.
Rules:
1. ALWAYS base your answers on this live snapshot balance and tracks list.
2. Answer in a clean, professional, and concise betting format.`;

        // Update activity to download
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai'
            ? { ...m, content: 'Initializing GPU / Loading model...' }
            : m
        ));

        // Get the engine and run
        const engine = await getWebLLMEngine(selectedModel, (p) => {
          setMessages(prev => prev.map((m, i) =>
            i === prev.length - 1 && m.role === 'ai'
              ? { ...m, content: `Loading: ${p.text} (${Math.round(p.progress * 100)}%)` }
              : m
          ));
        });

        clearInterval(actInterval);
        setCurrentActivity('🧠 Local GPU Processing...');

        // Clear the loading progress text so we can stream into it
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai'
            ? { ...m, content: '', activity: selectedModel }
            : m
        ));

        const chatHistory = messages.map(m => ({
          role: (m.role === 'ai' ? 'assistant' : 'user') as 'assistant' | 'user',
          content: m.content
        }));
        // Prepend system prompt
        const chatMessages = [
          { role: 'system' as const, content: systemPrompt },
          ...chatHistory,
          { role: 'user' as const, content: userMsg }
        ];

        const chatCompletion = await engine.chat.completions.create({
          messages: chatMessages,
          stream: true,
        });

        for await (const chunk of chatCompletion) {
          const delta = chunk.choices[0]?.delta?.content || '';
          if (delta) {
            setMessages(prev => prev.map((m, i) =>
              i === prev.length - 1 && m.role === 'ai'
                ? { ...m, content: m.content + delta }
                : m
            ));
          }
        }

        setLastModelUsed(selectedModel);

      } catch (err: any) {
        console.error('[WebLLM Error]', err);
        clearInterval(actInterval);
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai'
            ? { ...m, content: `WebLLM Error: ${err.message || err}` }
            : m
        ));
      } finally {
        clearInterval(actInterval);
        setLoading(false);
        setCurrentActivity(null);
      }
      return;
    }

    try {
      const modelVal = selectedModel !== 'auto' ? selectedModel : undefined;
      const modelUsed = modelVal || 'strike-tips';
      const res = await apiFetch('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [{ role: 'user', content: userMsg }],
          model: modelVal,
          stream: true,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      const readLoop = async () => {
        while (true) {
          const { done, value } = await reader.read();
          if (done) { clearInterval(actInterval); setCurrentActivity(null); break; }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6).trim();
            if (payload === '[DONE]') { clearInterval(actInterval); setCurrentActivity(null); continue; }
            try {
              const parsed = JSON.parse(payload);
              const delta = parsed.choices?.[0]?.delta?.content || '';
              const finish = parsed.choices?.[0]?.finish_reason;
              if (delta) {
                setMessages(prev => prev.map((m, i) =>
                  i === prev.length - 1 && m.role === 'ai'
                    ? { ...m, content: m.content + delta, activity: modelUsed }
                    : m
                ));
              }
              if (finish === 'stop') {
                const modelName = parsed.model || modelUsed;
                setLastModelUsed(modelName);
                clearInterval(actInterval);
                setCurrentActivity(null);
              }
            } catch {}
          }
        }
      };
      await readLoop();
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
      className="flex h-full min-h-[500px] bg-white/5 border border-white/10 rounded-3xl overflow-hidden backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] w-full"
    >
      {/* Session Sidebar — Hidden on mobile */}
      <div className="hidden md:flex w-44 border-r border-white/10 p-4 bg-black/20 flex-col gap-2 shrink-0">
        <div className="text-xs font-black uppercase text-purple-500 mb-2 tracking-widest">Sessions</div>
        {sessions.map(s => (
          <button key={s.id} className="text-sm text-left text-slate-400 hover:text-white hover:bg-white/5 p-2 rounded-lg truncate transition-all">
            {s.title}
          </button>
        ))}
        <div className="mt-auto flex flex-col gap-2 pt-4 border-t border-white/10">
          <button className="text-xs font-bold text-slate-600 hover:text-purple-400">Export Logs</button>
          <button onClick={() => { setMessages([]); localStorage.removeItem(STORAGE_KEY); }} className="text-xs font-bold text-red-500/60 hover:text-red-500">Clear Session</button>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="p-4 border-b border-white/10 bg-white/5 flex items-center justify-between gap-4 overflow-hidden">
            <div className="flex items-center gap-3 shrink-0">
              <Bot className="w-5 h-5 text-purple-400" />
              <span className="text-sm font-black uppercase tracking-widest text-white truncate">Strike Command</span>
            </div>
            {currentActivity && (
                <div className="px-3 py-1 bg-purple-500/10 border border-purple-500/30 rounded-full flex items-center gap-2 animate-pulse min-w-0">
                    <Loader2 className="w-3 h-3 text-purple-400 animate-spin shrink-0" />
                    <span className="text-xs font-bold text-purple-300 uppercase truncate">{currentActivity}</span>
                </div>
            )}
            <div className="flex gap-2 items-center shrink-0">
              <div className="px-2 py-1 bg-purple-900/30 border border-purple-500/50 rounded text-xs font-bold text-purple-300 uppercase">
                {currentActivity ? 'RUNNING' : 'ACTIVE'}
              </div>
              {lastModelUsed && (
                <div className="hidden sm:block px-2 py-1 bg-emerald-900/30 border border-emerald-500/40 rounded text-xs font-bold text-emerald-300 uppercase">
                  {lastModelUsed}
                </div>
              )}
            </div>
        </div>
        
        <div ref={scrollRef} className="flex-1 p-6 overflow-y-auto space-y-6 font-mono text-sm custom-scrollbar">
            {messages.length === 0 && (
                <div className="text-center text-slate-600 mt-20 italic text-sm uppercase tracking-wider">
                    Awaiting parameters...
                </div>
            )}
            {messages.map((m, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              key={i} 
              className={`flex flex-col gap-2 ${m.role === 'user' ? 'items-end' : ''}`}
            >
                <div className="text-xs text-slate-600 uppercase px-2">{m.timestamp}</div>
                <div className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''} w-full`}>
                    {m.role === 'ai' && <Bot className="w-5 h-5 text-purple-500 shrink-0 mt-1" />}
                    <div className={`p-4 rounded-2xl max-w-[85%] break-words ${m.role === 'user' ? 'bg-purple-600/90 text-white shadow-[0_0_15px_rgba(168,85,247,0.2)] ml-auto' : 'bg-white/5 text-slate-300 border border-white/10 shadow-[0_0_15px_rgba(0,0,0,0.15)] mr-auto'}`}>
                      {m.content}
                    </div>
                    {m.role === 'user' && <User className="w-5 h-5 text-slate-500 shrink-0 mt-1" />}
                </div>
            </motion.div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <Bot className="w-5 h-5 text-purple-500 animate-pulse" />
                <Loader2 className="w-5 h-5 animate-spin text-purple-500" />
              </div>
            )}
        </div>

        <div className="p-4 border-t border-white/10 bg-black/40 flex flex-col sm:flex-row gap-3">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-black/20 border border-white/10 rounded-xl px-3 py-2 text-sm text-white font-bold focus:outline-none focus:ring-2 focus:ring-purple-500/50 w-full sm:w-auto min-h-[40px]"
              >
                <option value="auto" className="bg-black">⚡ Auto Router</option>
                <optgroup label="☁️ Cloud">
                  <option value="groq" className="bg-black">Groq Llama 70B</option>
                  <option value="gemini" className="bg-black">Gemini Flash</option>
                </optgroup>
                <optgroup label="🌐 Browser Local (WebGPU)">
                  <option value="webllm-qwen-0.5b" className="bg-black text-xs" disabled={!webGpuSupported}>
                    Qwen 2.5 0.5B {!webGpuSupported ? '❌ (No WebGPU)' : '⚡'}
                  </option>
                  <option value="webllm-llama-1b" className="bg-black text-xs" disabled={!webGpuSupported}>
                    Llama 3.2 1B {!webGpuSupported ? '❌ (No WebGPU)' : '⚡'}
                  </option>
                  <option value="webllm-qwen-1.5b" className="bg-black text-xs" disabled={!webGpuSupported}>
                    Qwen 2.5 1.5B {!webGpuSupported ? '❌ (No WebGPU)' : '⚡'}
                  </option>
                </optgroup>
              </select>
            <div className="flex gap-2 flex-1 w-full min-w-0">
              <textarea 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Type command..."
                aria-label="Chat input"
                className="flex-1 bg-black/20 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-colors min-h-[40px] max-h-[150px] resize-none overflow-y-auto"
                rows={1}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = `${target.scrollHeight}px`;
                }}
              />
              <button 
                onClick={sendMessage} 
                aria-label="Send message"
                className="bg-purple-600 px-4 rounded-xl hover:bg-purple-500 transition-all font-black uppercase text-sm tracking-wider shadow-[0_0_15px_rgba(168,85,247,0.3)] shrink-0 min-h-[40px] self-start"
              >
                Send
              </button>
            </div>
        </div>
      </div>
    </motion.div>
  );
};