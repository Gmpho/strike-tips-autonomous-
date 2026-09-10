import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, Loader2, Plus, Trash2, StopCircle, Menu, X, FileText, Volume2, Languages, ImagePlus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../lib/api-fetch';
import { checkWebGPUSupport, getWebLLMEngine, resetWebLLMEngine } from '../lib/webllm';
import { useTTS } from '../hooks/useTTS';
import { useTranslation } from '../hooks/useTranslation';
import { useFormReader } from '../hooks/useFormReader';
import type { RaceEvent, Runner } from '../types';

const SESSIONS_STORAGE_KEY = 'strike_chat_sessions';
const ACTIVE_SESSION_KEY = 'strike_active_chat_session';

// Summarize mode: reuses whatever model is selected (on-device Qwen when
// available — zero download, zero server cost) with a summarizer brief
// instead of the racing-analyst brief. No RAG context is fetched.
const SUMMARIZER_SYSTEM_PROMPT = `You are a precise summarizer. Summarize the user's pasted text in 3-6 tight bullet points, then one single-line bottom line. No betting advice, no preamble.`;

interface Session {
  id: string;
  title: string;
  timestamp: number;
}

interface Message {
  role: 'user' | 'ai';
  content: string;
  timestamp: string;
  activity?: string;
}

function formatRaceCardPrompt(event: RaceEvent, focusRunner?: Runner): string {
  const runnersText = event.runners
    .map((r, i) => {
      const odds = typeof r.odds === 'number' ? r.odds.toFixed(2) : r.odds || 'SP';
      const jockey = r.jockeyName || 'TBA';
      const trainer = r.trainerName || 'TBA';
      return `${i + 1}. ${r.name} — ${odds} — Form: ${r.form || 'N/A'} — ${jockey} / ${trainer}`;
    })
    .join('\n');
  const focusLine = focusRunner ? `\nFOCUS RUNNER: ${focusRunner.name}${typeof focusRunner.odds === 'number' ? ` @ ${focusRunner.odds.toFixed(2)}` : ''} — analyse this runner's value case in depth (form, draw, jockey/trainer stats, and how it compares to the field below).\n` : '';
  return `Analyse this race for value betting opportunities:

Course: ${event.course} | Race ${event.raceNumber} | Off Time: ${event.t}${focusLine}
Runners:
${runnersText}

${focusRunner ? `Assess whether ${focusRunner.name} represents a value bet versus the rest of the field, then flag any alternative selections.` : 'Identify the best value selection, estimate the probability edge, and flag any high-strike-rate jockey/trainer combos.'}`;
}

export interface AIChatProps {
  initialRaceEvent?: RaceEvent;
  initialRunner?: Runner;
}

export const AIChat: React.FC<AIChatProps> = ({ initialRaceEvent, initialRunner }) => {
  // 1. Sessions State Management

  const [sessions, setSessions] = useState<Session[]>(() => {
    try {
      const saved = localStorage.getItem(SESSIONS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) return parsed;
      }
    } catch {}
    return [{ id: 'default', title: 'New Chat Session', timestamp: Date.now() }];
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const lastActive = localStorage.getItem(ACTIVE_SESSION_KEY);
    return lastActive || 'default';
  });

  // 2. Messages State Management (by Session ID)
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentActivity, setCurrentActivity] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('auto');
  const [summarizeMode, setSummarizeMode] = useState(false);
  const [toolNote, setToolNote] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const tts = useTTS();
  const mt = useTranslation();
  const formReader = useFormReader();

  const flashNote = (text: string | null) => {
    setToolNote(text);
    if (text) {
      window.setTimeout(() => {
        setToolNote((cur) => (cur === text ? null : cur));
      }, 5000);
    }
  };

  const onSpeakMessage = async (content: string) => {
    const ok = await tts.speak(content);
    if (!ok) flashNote('Voice not ready — first use downloads ~130MB (use Wi-Fi).');
  };

  const onTranslateMessage = async (index: number, content: string) => {
    const out = await mt.translate(content);
    if (!out) {
      flashNote('Translation unavailable offline right now.');
      return;
    }
    const label = mt.langs.find((l) => l.id === mt.langId)?.label ?? mt.langId;
    setMessages((prev) =>
      prev.map((m, i) => (i === index ? { ...m, content: `${m.content}\n\n[${label}]\n${out}` } : m))
    );
  };

  const onImagePicked = async (file: File | undefined) => {
    if (!file) return;
    if (fileRef.current) fileRef.current.value = '';
    flashNote('Reading form image on-device…');
    const text = await formReader.readImage(file);
    if (text) {
      setInput((prev) => (prev ? `${prev}\n\n` : '') + `[Form image]\n${text}`);
      flashNote(null);
    } else {
      flashNote('Could not read that image — try a closer crop of the text.');
    }
  };
  const [lastModelUsed, setLastModelUsed] = useState<string | null>(null);
  const [webGpuSupported, setWebGpuSupported] = useState(false);
  // Weak GPUs (≤4GB device RAM hint) can't hold 1.7B+ models without hanging
  // the whole machine — those options stay disabled (same pattern as no-WebGPU).
  const [weakGpu, setWeakGpu] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false); // Mobile Drawer State

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const actIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prefetchedContextRef = useRef<string | null>(null);
  const contextAbortRef = useRef<AbortController | null>(null);
  // Stream batching: tokens accumulate here and flush to React state at
  // 10Hz. Per-token setState + full-list re-render + disk persist on every
  // token is what locked the main thread (and the whole PC on weak GPUs).
  const streamBufRef = useRef('');
  const flushTimerRef = useRef<number | null>(null);
  // Auto-scroll sticks to bottom unless the user scrolled up to read back.
  const stickRef = useRef(true);

  const stopStreamFlush = (flush = true) => {
    if (flushTimerRef.current) {
      window.clearInterval(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    if (flush && streamBufRef.current) {
      const chunk = streamBufRef.current;
      streamBufRef.current = '';
      setMessages((prev) =>
        prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai' ? { ...m, content: m.content + chunk } : m
        )
      );
    } else {
      streamBufRef.current = '';
    }
  };

  const startStreamFlush = () => {
    stopStreamFlush(false);
    flushTimerRef.current = window.setInterval(() => {
      if (!streamBufRef.current) return;
      const chunk = streamBufRef.current;
      streamBufRef.current = '';
      setMessages((prev) =>
        prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai' ? { ...m, content: m.content + chunk } : m
        )
      );
    }, 100);
  };

  // Sync active view support
  useEffect(() => {
    checkWebGPUSupport().then(supported => {
      setWebGpuSupported(supported);
      if (supported) {
        const gb = (navigator as unknown as { deviceMemory?: number }).deviceMemory;
        if (typeof gb === 'number' && gb <= 4) setWeakGpu(true);
      }
    });
  }, []);

  // Pre-fill textarea with race card prompt when launched from Execute Position
  useEffect(() => {
    if (!initialRaceEvent) return;
    const prompt = formatRaceCardPrompt(initialRaceEvent, initialRunner);
    const sessionTitle = `${initialRaceEvent.course} R${initialRaceEvent.raceNumber}${initialRunner ? ` · ${initialRunner.name}` : ''}`;
    const newId = `race_${initialRaceEvent.id}_${Date.now()}`;
    const newSession: Session = { id: newId, title: sessionTitle, timestamp: Date.now() };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
    setInput(prompt);
    // Resize textarea to fit the pre-filled content
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
      }
    }, 50);
  }, [initialRaceEvent, initialRunner]);


  // Dispatch WebGPU activity event to pause Three.js rendering during local inference
  useEffect(() => {
    const isWebgpu = selectedModel.startsWith('webllm-');
    window.dispatchEvent(new CustomEvent('webgpu-activity', {
      detail: { active: loading && isWebgpu }
    }));
  }, [loading, selectedModel]);

  // Sync session list to localStorage
  useEffect(() => {
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  // Load messages whenever activeSessionId changes
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`strike_chat_messages_${activeSessionId}`);
      setMessages(saved ? JSON.parse(saved) : []);
    } catch {
      setMessages([]);
    }
    // Sync active session ID to localStorage
    localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
  }, [activeSessionId]);

  // Save messages when they change — debounced and capped. Persisting the
  // full history synchronously on EVERY streamed token stalled the main
  // thread (fatal on full disks). 2s idle flush of the last 50 is plenty.
  const persistTimerRef = useRef<number | null>(null);
  useEffect(() => {
    if (!activeSessionId) return;
    if (persistTimerRef.current) window.clearTimeout(persistTimerRef.current);
    persistTimerRef.current = window.setTimeout(() => {
      try {
        const capped = messages.slice(-50);
        localStorage.setItem(`strike_chat_messages_${activeSessionId}`, JSON.stringify(capped));
      } catch {}
    }, 2000);
    return () => {
      if (persistTimerRef.current) window.clearTimeout(persistTimerRef.current);
    };
  }, [messages, activeSessionId]);

  // Scroll to bottom via rAF, and only while stuck to bottom. Previously ran
  // a layout-measuring scrollTo on every token even while reading history.
  useEffect(() => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    const doScroll = () => {
      if (!stickRef.current) return;
      el.scrollTo({
        top: el.scrollHeight,
        behavior: loading ? 'auto' : 'smooth'
      });
    };
    if (loading) requestAnimationFrame(doScroll);
    else doScroll();
  }, [messages, currentActivity, loading]);

  // Debounced context prefetch while user types. Skipped while generating:
  // a background fetch + JSON parse mid-generation is main-thread work the
  // GPU-busy tab cannot afford, and its result is never used mid-flight.
  useEffect(() => {
    if (!input.trim() || loading) {
      return;
    }
    const timer = setTimeout(async () => {
      if (contextAbortRef.current) {
        contextAbortRef.current.abort();
      }
      const controller = new AbortController();
      contextAbortRef.current = controller;
      try {
        const res = await apiFetch(
          `/api/agent/context?query=${encodeURIComponent(input)}&session_id=${activeSessionId}`,
          { signal: controller.signal }
        );
        if (res.ok) {
          const data = await res.json();
          if (data.success && data.context) {
            prefetchedContextRef.current = data.context;
          }
        }
      } catch (e: any) {
        if (e.name !== 'AbortError') {
          console.warn('[Context Prefetch]', e);
        }
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [input, activeSessionId, apiFetch, loading]);

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

  // Create New Session
  const createNewSession = () => {
    const newId = `session_${Date.now()}`;
    const newSession: Session = {
      id: newId,
      title: 'New Chat Session',
      timestamp: Date.now()
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
  };

  // Delete Session
  const deleteSession = (idToDelete: string) => {
    setSessions(prev => {
      const updated = prev.filter(s => s.id !== idToDelete);
      if (activeSessionId === idToDelete && updated.length > 0) {
        setActiveSessionId(updated[0].id);
      }
      return updated;
    });
    localStorage.removeItem(`strike_chat_messages_${idToDelete}`);
  };

  // Clear Active Session Messages
  const clearActiveSession = () => {
    setMessages([]);
    localStorage.removeItem(`strike_chat_messages_${activeSessionId}`);
  };

  // Stop Generation
  const stopGeneration = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopStreamFlush();
    if (selectedModel.startsWith('webllm-')) {
      try {
        const engine = await getWebLLMEngine(selectedModel);
        await engine.interruptGenerate();
      } catch (e) {
        console.warn("Interrupting WebLLM failed:", e);
      }
    }
    if (actIntervalRef.current) {
      clearInterval(actIntervalRef.current);
    }
    setLoading(false);
    setCurrentActivity(null);
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input;
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Create new message array
    const updatedMessages: Message[] = [...messages, { role: 'user', content: userMsg, timestamp: now }];
    setMessages(updatedMessages);
    setInput('');
    stickRef.current = true;
    if (textareaRef.current) {
      textareaRef.current.style.height = '48px';
    }
    setLoading(true);

    // Auto-generate session title if this is the first message
    if (messages.length === 0) {
      const displayTitle = userMsg.length > 22 ? userMsg.slice(0, 20) + '...' : userMsg;
      setSessions(prev => prev.map(s => s.id === activeSessionId ? { ...s, title: displayTitle } : s));
    }

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
    actIntervalRef.current = actInterval;

    // Add empty AI message that we'll stream into
    setMessages(prev => [...prev, { role: 'ai', content: '', timestamp: now }]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (selectedModel.startsWith('webllm-')) {
      try {
        // Fetch server-compiled context (snapshot events, vector guides, web search results)
        let compiledContext = '';
        if (summarizeMode) {
          // Summaries run on the pasted text alone — no RAG fetch, no history.
          prefetchedContextRef.current = null;
        } else if (prefetchedContextRef.current) {
          compiledContext = prefetchedContextRef.current;
          prefetchedContextRef.current = null;
        } else {
          try {
            const contextRes = await apiFetch(
              `/api/agent/context?query=${encodeURIComponent(userMsg)}&session_id=${activeSessionId}`
            );
            if (contextRes.ok) {
              const data = await contextRes.json();
              if (data.success && data.context) {
                compiledContext = data.context;
              }
            }
          } catch (e) {
            console.warn('[WebLLM Server Context Fetch Failed]', e);
          }
        }

        if (controller.signal.aborted) return;

        const systemPrompt = summarizeMode
          ? SUMMARIZER_SYSTEM_PROMPT
          : `You are Strike Tips Racing AI, a helpful, private on-device assistant. Answer concisely and accurately.
Rules:
1. ALWAYS base your answers on the live compiled context provided below.
2. Answer in a clean, professional, and concise betting format.

[LIVE RESEARCH & CONTEXT DATA]
${compiledContext || 'No context data available.'}`;

        // Update activity to download
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai'
            ? { ...m, content: 'Initializing GPU / Loading model...' }
            : m
        ));

        // Get the engine and run
        const engine = await getWebLLMEngine(selectedModel, (p) => {
          if (controller.signal.aborted) return;
          setMessages(prev => prev.map((m, i) =>
            i === prev.length - 1 && m.role === 'ai'
              ? { ...m, content: `Loading: ${p.text} (${Math.round(p.progress * 100)}%)` }
              : m
          ));
        });

        if (controller.signal.aborted) return;

        clearInterval(actInterval);
        setCurrentActivity('🧠 Local GPU Processing...');

        // Clear the loading progress text so we can stream into it
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai'
            ? { ...m, content: '', activity: selectedModel }
            : m
        ));

        const chatHistory = updatedMessages.map(m => ({
          role: (m.role === 'ai' ? 'assistant' : 'user') as 'assistant' | 'user',
          content: m.content
        }));

        const chatMessages = summarizeMode
          ? [
              { role: 'system' as const, content: systemPrompt },
              { role: 'user' as const, content: userMsg },
            ]
          : [
              { role: 'system' as const, content: systemPrompt },
              ...chatHistory
            ];

        const chatCompletion = await engine.chat.completions.create({
          messages: chatMessages,
          stream: true,
        });
        startStreamFlush();

        for await (const chunk of chatCompletion) {
          if (controller.signal.aborted) break;
          const delta = chunk.choices[0]?.delta?.content || '';
          if (delta) streamBufRef.current += delta;
        }

        setLastModelUsed(selectedModel);

      } catch (err: any) {
        if (controller.signal.aborted) {
          console.log("[WebLLM] Generation stopped by user.");
          return;
        }
        console.error('[WebLLM Error]', err);
        clearInterval(actInterval);
        resetWebLLMEngine();

        const errMsg = String(err.message || err).toLowerCase();
        let displayError = `WebLLM Error: ${err.message || err}`;

        if (errMsg.includes("quota") || errMsg.includes("storage")) {
          displayError = "💾 **WebLLM Storage Error**: Exceeded browser disk space quota. The model weights are too large to save. " +
            "Please clear storage space or click 'Reset Browser AI Storage' in Settings to clear old cache files, " +
            "or switch to the lighter Qwen 2.5 0.5B model.";
        } else if (
          errMsg.includes("device") || 
          errMsg.includes("instance") || 
          errMsg.includes("lost") || 
          errMsg.includes("mapasync") ||
          errMsg.includes("gpubuffer")
        ) {
          displayError = "🔌 **WebGPU Device Lost**: Your graphics card ran out of VRAM or crashed while running the model. " +
            "Switched you to the lighter **Qwen 2.5 0.5B** — try again with it.";
          try {
            await resetWebLLMEngine();
          } catch {}
          setSelectedModel('webllm-qwen-0.5b');
        } else if (errMsg.includes("json")) {
          displayError = "⚠️ **WebLLM Cache Corruption**: Detected a corrupted download config. " +
            "Please go to Settings and click 'Reset Browser AI Storage' to clear the corrupted cache and start fresh.";
        }

        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 && m.role === 'ai'
            ? { ...m, content: displayError }
            : m
        ));
      } finally {
        clearInterval(actInterval);
        setLoading(false);
        setCurrentActivity(null);
        abortControllerRef.current = null;
        stopStreamFlush();
      }
      return;
    }

    // Cloud / Auto-Router API fetch
    try {
      const modelVal = selectedModel !== 'auto' ? selectedModel : undefined;
      const modelUsed = modelVal || 'strike-tips';
      const res = await apiFetch('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
        body: JSON.stringify({
          messages: [
            ...(summarizeMode
              ? [{ role: 'system', content: SUMMARIZER_SYSTEM_PROMPT }]
              : []),
            ...updatedMessages.map(m => ({
              role: m.role === 'ai' ? 'assistant' : 'user',
              content: m.content
            })),
          ],
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
      startStreamFlush();

      while (true) {
        if (controller.signal.aborted) {
          await reader.cancel();
          break;
        }
        const { done, value } = await reader.read();
        if (done) { 
          clearInterval(actInterval); 
          setCurrentActivity(null); 
          break; 
        }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') { 
            clearInterval(actInterval); 
            setCurrentActivity(null); 
            continue; 
          }
          try {
            const parsed = JSON.parse(payload);
            const delta = parsed.choices?.[0]?.delta?.content || '';
            const finish = parsed.choices?.[0]?.finish_reason;
            if (delta) {
              streamBufRef.current += delta;
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
    } catch (err: any) {
      if (controller.signal.aborted) {
        console.log("[Chat] Generation stopped by user.");
        return;
      }
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
      abortControllerRef.current = null;
      stopStreamFlush();
    }
  };

  const renderSidebarContents = () => (
    <>
      <button 
        onClick={() => { createNewSession(); setIsSidebarOpen(false); }}
        className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/25 border-purple-500/40 rounded-xl text-purple-300 hover:text-white transition-all text-xs font-black uppercase tracking-wider mb-3 shrink-0"
      >
        <Plus className="w-4 h-4" /> New Chat
      </button>
      
      <div className="flex-1 overflow-y-auto pr-1 space-y-1.5 custom-scrollbar min-h-0">
        {sessions.map(s => (
          <div key={s.id} className="group relative flex items-center justify-between rounded-xl overflow-hidden">
            <button 
              onClick={() => { setActiveSessionId(s.id); setIsSidebarOpen(false); }} 
              className={`flex-1 text-xs text-left px-3 py-2.5 truncate font-bold transition-all ${
                activeSessionId === s.id 
                  ? 'text-white bg-purple-500/25 border border-purple-500/30' 
                  : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'
              } rounded-xl`}
            >
              {s.title}
            </button>
            {sessions.length > 1 && (
              <button 
                onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                className="absolute right-2 p-1.5 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity bg-black/80 rounded-lg border border-white/5"
                title="Delete chat session"
                aria-label={`Delete chat session ${s.title}`}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="pt-4 border-t border-white/10 shrink-0 flex flex-col gap-2 mt-auto">
        <button 
          onClick={clearActiveSession} 
          className="w-full py-2.5 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-xl text-xs font-bold transition-all uppercase tracking-wider"
        >
          Clear Chat Messages
        </button>
      </div>
    </>
  );

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex h-[calc(100dvh-190px)] md:h-[calc(100vh-200px)] min-h-[460px] bg-white/5 border border-white/10 rounded-2xl sm:rounded-3xl overflow-hidden backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] w-full relative"
    >
      {/* 1. Desktop Session Sidebar */}
      <div className="hidden md:flex w-52 border-r border-white/10 p-4 bg-black/20 flex-col gap-2 shrink-0">
        <div className="text-xs font-black uppercase text-purple-500 mb-2 tracking-widest px-1">Sessions</div>
        {renderSidebarContents()}
      </div>

      {/* 2. Mobile Session Drawer (Backdrop + Menu) */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsSidebarOpen(false)}
            className="md:hidden fixed inset-0 bg-black/80 backdrop-blur-sm z-40"
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div 
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="md:hidden fixed inset-y-0 left-0 w-64 bg-[#0a0712] border-r border-white/10 p-4 z-50 flex flex-col gap-2"
          >
            <div className="flex items-center justify-between mb-4 shrink-0">
              <span className="text-xs font-black uppercase text-purple-500 tracking-widest px-1">Sessions</span>
              <button onClick={() => setIsSidebarOpen(false)} aria-label="Close sessions panel" className="p-1.5 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            {renderSidebarContents()}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3. Main Chat Panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat Header */}
        <div className="p-4 border-b border-white/10 bg-white/5 flex items-center justify-between gap-4 overflow-hidden shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              {/* Menu toggle for mobile history drawer */}
              <button 
                onClick={() => setIsSidebarOpen(true)}
                className="md:hidden p-2 hover:bg-white/5 border border-white/10 rounded-xl text-slate-300 transition-colors shrink-0"
                title="View sessions history"
                aria-label="Open sessions history"
              >
                <Menu className="w-4.5 h-4.5" />
              </button>
              
              <Bot className="w-5 h-5 text-purple-400 shrink-0" />
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
                {loading ? 'RUNNING' : 'ACTIVE'}
              </div>
              {lastModelUsed && (
                <div className="hidden sm:block px-2 py-1 bg-emerald-900/30 border border-emerald-500/40 rounded text-xs font-bold text-emerald-300 uppercase">
                  {lastModelUsed}
                </div>
              )}
              {/* Mobile and Desktop Accessible Clean/Clear Chat Button */}
              <button 
                onClick={clearActiveSession}
                title="Clear current chat messages"
                aria-label="Clear current chat messages"
                className="p-2 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 rounded-xl text-red-400 hover:text-red-300 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
        </div>
        
        {/* Messages view */}
        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          }}
          className="flex-1 p-6 overflow-y-auto space-y-6 font-mono text-sm custom-scrollbar bg-black/10"
        >
            {messages.length === 0 && (
                <div className="text-center text-slate-600 mt-20 italic text-sm uppercase tracking-wider select-none">
                    Awaiting parameters...
                </div>
            )}
            {messages.map((m, i) => (
            <div 
              key={i} 
              className={`flex flex-col gap-2 ${m.role === 'user' ? 'items-end' : ''} ${
                i === messages.length - 1 ? 'animate-chat-fade-in-up' : ''
              }`}
            >
                <div className="text-[10px] text-slate-600 uppercase px-2 font-bold select-none">{m.timestamp}</div>
                <div className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''} w-full`}>
                    {m.role === 'ai' && <Bot className="w-5 h-5 text-purple-500 shrink-0 mt-1" />}
                    <div className={`p-4 rounded-2xl max-w-[85%] break-words leading-relaxed ${
                      m.role === 'user' 
                        ? 'bg-purple-600/90 text-white shadow-[0_0_15px_rgba(168,85,247,0.2)] ml-auto border border-purple-500/30' 
                        : 'bg-white/5 text-slate-300 border border-white/10 shadow-[0_0_15px_rgba(0,0,0,0.15)] mr-auto'
                    }`}>
                      {m.role === 'ai' && m.content === '' && loading && i === messages.length - 1 ? (
                        <div className="flex items-center gap-2 text-slate-400 text-xs py-1 px-0.5">
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                          <span className="animate-pulse">Thinking...</span>
                        </div>
                      ) : m.role === 'ai' && (m.content.startsWith('Loading:') || m.content.startsWith('Initializing')) && i === messages.length - 1 ? (
                        <div className="flex flex-col gap-2.5 min-w-[240px] py-1">
                          <div className="flex items-center justify-between text-xs text-purple-400 font-bold">
                            <span className="flex items-center gap-1.5">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              GPU AI Core Loading...
                            </span>
                            <span>
                              {m.content.includes('%') ? m.content.match(/\d+%/)?.[0] || '' : ''}
                            </span>
                          </div>
                          <div className="w-full bg-white/5 border border-white/5 rounded-full h-2 overflow-hidden">
                            <motion.div 
                              className="bg-gradient-to-r from-purple-500 to-indigo-500 h-full rounded-full"
                              initial={{ width: 0 }}
                              animate={{ 
                                width: m.content.includes('%') 
                                  ? `${parseInt(m.content.match(/\d+/)?.[0] || '0')}%` 
                                  : '30%' 
                              }}
                              transition={{ duration: 0.2 }}
                            />
                          </div>
                          <span className="text-[11px] text-slate-400 leading-normal italic font-medium">
                            {m.content}
                          </span>
                        </div>
                      ) : (
                        m.content
                      )}
                    </div>
                    {m.role === 'user' && <User className="w-5 h-5 text-slate-500 shrink-0 mt-1" />}
                </div>
                {m.role === 'ai' && m.content && !m.content.startsWith('Loading:') && !m.content.startsWith('Initializing') && (
                  <div className="flex gap-1.5 pl-8">
                    <button
                      onClick={() => void onSpeakMessage(m.content)}
                      title={`Read aloud (${tts.voiceId.toUpperCase()} voice)`}
                      aria-label="Read this verdict aloud"
                      className="p-1.5 rounded-lg bg-white/5 border border-white/10 text-theme-secondary hover:text-purple-300 hover:border-purple-500/30 transition-all"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => void onTranslateMessage(i, m.content)}
                      title={`Translate to ${mt.langs.find((l) => l.id === mt.langId)?.label ?? mt.langId} on-device`}
                      aria-label="Translate this verdict"
                      className="p-1.5 rounded-lg bg-white/5 border border-white/10 text-theme-secondary hover:text-purple-300 hover:border-purple-500/30 transition-all"
                    >
                      <Languages className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
            </div>
            ))}
        </div>

        {/* On-device AI toolbar: target language, voice, form-image reader */}
        <div className="px-4 pt-3 flex items-center gap-2 text-xs shrink-0">
          <select
            value={mt.langId}
            onChange={(e) => mt.setLangId(e.target.value as 'af' | 'zu' | 'st')}
            title="Translate verdicts to… (downloaded once, then offline)"
            aria-label="Translation language"
            className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-[11px] text-white font-bold focus:outline-none focus:ring-2 focus:ring-purple-500/50"
          >
            {mt.langs.map((l) => (
              <option key={l.id} value={l.id} className="bg-[#0c0817]">
                {l.label}
              </option>
            ))}
          </select>
          <button
            onClick={tts.cycleVoice}
            title="Tap to switch voice (2 female, 1 male — English)"
            aria-label="Switch voice"
            className="px-2.5 py-1.5 rounded-lg bg-white/5 border border-white/10 text-theme-secondary hover:text-purple-300 hover:border-purple-500/30 transition-all font-black text-[11px]"
          >
            {tts.voiceId.toUpperCase()}
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            title="Attach a form/racecard image to read its text"
            aria-label="Attach form image"
            className="p-1.5 rounded-lg bg-white/5 border border-white/10 text-theme-secondary hover:text-purple-300 hover:border-purple-500/30 transition-all"
          >
            <ImagePlus className="w-4 h-4" />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
            onChange={(e) => void onImagePicked(e.target.files?.[0])}
          />
          {(tts.busy || tts.speaking || mt.translating || formReader.reading) && (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
          )}
          {toolNote && (
            <span className="text-[11px] text-slate-400 font-semibold truncate">{toolNote}</span>
          )}
        </div>

        {/* Input box */}
        <div className="p-4 border-t border-white/10 bg-black/40 flex flex-col sm:flex-row gap-3 shrink-0">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-[#0c0817] border border-white/10 rounded-xl px-3 py-2 text-sm text-white font-bold focus:outline-none focus:ring-2 focus:ring-purple-500/50 w-full sm:w-auto min-h-[48px]"
              >
                <option value="auto" className="bg-[#0c0817]">⚡ Auto Router</option>
                <optgroup label="☁️ Cloud" className="bg-[#0c0817]">
                  <option value="groq" className="bg-[#0c0817]">Groq Llama 70B</option>
                  <option value="gemini" className="bg-[#0c0817]">Gemini Flash</option>
                </optgroup>
                <optgroup label="🌐 Browser Local (WebGPU)" className="bg-[#0c0817]">
                  <option value="webllm-qwen-0.5b" className="bg-[#0c0817] text-xs" disabled={!webGpuSupported}>
                    Qwen 2.5 0.5B {!webGpuSupported ? '❌ (No WebGPU)' : '⚡'}
                  </option>
                  <option value="webllm-llama-1b" className="bg-[#0c0817] text-xs" disabled={!webGpuSupported}>
                    Llama 3.2 1B {!webGpuSupported ? '❌ (No WebGPU)' : '⚡'}
                  </option>
                  <option value="webllm-qwen-1.5b" className="bg-[#0c0817] text-xs" disabled={!webGpuSupported}>
                    Qwen 2.5 1.5B {!webGpuSupported ? '❌ (No WebGPU)' : '⚡'}
                  </option>
                  <option value="webllm-qwen3-1.7b" className="bg-[#0c0817] text-xs" disabled={!webGpuSupported || weakGpu}>
                    Qwen3 1.7B {!webGpuSupported ? '❌ (No WebGPU)' : weakGpu ? '❌ (Weak GPU)' : '⚡'}
                  </option>
                  <option value="webllm-qwen35-2b" className="bg-[#0c0817] text-xs" disabled={!webGpuSupported || weakGpu}>
                    Qwen3.5 2B {!webGpuSupported ? '❌ (No WebGPU)' : weakGpu ? '❌ (Weak GPU)' : '⚡'}
                  </option>
                </optgroup>
              </select>
              
            <div className="flex gap-2 flex-1 w-full min-w-0 items-start">
              <button
                onClick={() => setSummarizeMode(v => !v)}
                aria-pressed={summarizeMode}
                title={summarizeMode ? 'Summarize mode on: pasted text gets bullet summaries' : 'Turn on summarize mode for pasted articles and reports'}
                className={`shrink-0 min-h-[48px] px-3 rounded-xl border transition-all flex items-center justify-center self-start ${
                  summarizeMode
                    ? 'bg-purple-500/25 border-purple-500/50 text-purple-200'
                    : 'bg-white/5 border-white/10 text-theme-secondary hover:text-theme-primary'
                }`}
              >
                <FileText className="w-4 h-4" />
              </button>
              <textarea 
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder={summarizeMode ? "Paste article or report to summarize..." : "Type command..."}
                aria-label="Chat input"
                className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all min-h-[48px] max-h-[150px] resize-none overflow-y-auto custom-scrollbar leading-relaxed"
                style={{ height: '48px' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = '48px';
                  target.style.height = `${Math.min(target.scrollHeight, 150)}px`;
                }}
              />
              {loading ? (
                <button 
                  onClick={stopGeneration} 
                  aria-label="Stop generation"
                  className="bg-red-600 hover:bg-red-500 px-4 rounded-xl transition-all font-black uppercase text-sm tracking-wider shadow-[0_0_15px_rgba(239,68,68,0.3)] shrink-0 min-h-[48px] flex items-center justify-center gap-1.5 self-start text-white"
                >
                  <StopCircle className="w-4 h-4" /> Stop
                </button>
              ) : (
                <button 
                  onClick={sendMessage} 
                  aria-label="Send message"
                  className="bg-purple-600 hover:bg-purple-500 px-4 rounded-xl transition-all font-black uppercase text-sm tracking-wider shadow-[0_0_15px_rgba(168,85,247,0.3)] shrink-0 min-h-[48px] flex items-center justify-center self-start text-white"
                >
                  Send
                </button>
              )}
            </div>
        </div>
      </div>
    </motion.div>
  );
};