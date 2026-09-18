import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, X, Radio, Volume2, Sparkles, AlertCircle } from 'lucide-react';

interface LiveVoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LiveVoiceModal: React.FC<LiveVoiceModalProps> = ({ isOpen, onClose }) => {
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'speaking' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [liveCaption, setLiveCaption] = useState<string>('');

  const wsRef = useRef<WebSocket | null>(null);
  const inputAudioCtxRef = useRef<AudioContext | null>(null);
  const outputAudioCtxRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const isMutedRef = useRef(false);
  isMutedRef.current = isMuted;

  const nextStartTimeRef = useRef(0);
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const animFrameRef = useRef<number | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);

  // Stop all current audio outputs
  const stopAudioPlayback = () => {
    activeSourcesRef.current.forEach(src => {
      try {
        src.stop();
        src.disconnect();
      } catch {}
    });
    activeSourcesRef.current = [];
    if (outputAudioCtxRef.current) {
      nextStartTimeRef.current = outputAudioCtxRef.current.currentTime;
    }
  };

  // Convert raw 24kHz linear 16-bit PCM base64 string to AudioBuffer and schedule
  const playPcmChunk = (base64Data: string) => {
    try {
      if (!outputAudioCtxRef.current) {
        outputAudioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
        nextStartTimeRef.current = outputAudioCtxRef.current.currentTime;
      }
      const ctx = outputAudioCtxRef.current;
      if (ctx.state === 'suspended') {
        ctx.resume();
      }

      const binaryStr = atob(base64Data);
      const len = binaryStr.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
      }

      const int16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
      }

      const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
      audioBuffer.copyToChannel(float32, 0);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      const currentTime = ctx.currentTime;
      if (nextStartTimeRef.current < currentTime) {
        nextStartTimeRef.current = currentTime;
      }

      source.start(nextStartTimeRef.current);
      nextStartTimeRef.current += audioBuffer.duration;

      activeSourcesRef.current.push(source);
      setStatus('speaking');

      source.onended = () => {
        activeSourcesRef.current = activeSourcesRef.current.filter(s => s !== source);
        if (activeSourcesRef.current.length === 0) {
          setStatus('connected');
        }
      };
    } catch (e) {
      console.warn('[PCM playback error]', e);
    }
  };

  const startSession = async () => {
    setStatus('connecting');
    setErrorMessage(null);
    setLiveCaption('');

    try {
      // 1. Setup WebSocket to Vite/Server /api/live
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/live`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        console.log('[Live WS Open]');
        // 2. Setup Mic Capture (16kHz PCM)
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              channelCount: 1,
              sampleRate: 16000,
              echoCancellation: true,
              noiseSuppression: true,
            },
          });
          mediaStreamRef.current = stream;

          const inCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
          inputAudioCtxRef.current = inCtx;

          const sourceNode = inCtx.createMediaStreamSource(stream);
          const processorNode = inCtx.createScriptProcessor(4096, 1, 1);
          processorRef.current = processorNode;

          sourceNode.connect(processorNode);
          processorNode.connect(inCtx.destination);

          processorNode.onaudioprocess = (e) => {
            if (isMutedRef.current || ws.readyState !== WebSocket.OPEN) return;

            const float32 = e.inputBuffer.getChannelData(0);

            // Compute audio level for UI animation
            let sum = 0;
            for (let i = 0; i < float32.length; i++) {
              sum += Math.abs(float32[i]);
            }
            const avg = sum / float32.length;
            setAudioLevel(Math.min(100, Math.round(avg * 400)));

            // Convert Float32 to linear 16-bit PCM
            const pcm16 = new Int16Array(float32.length);
            for (let i = 0; i < float32.length; i++) {
              const s = Math.max(-1, Math.min(1, float32[i]));
              pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            const bytes = new Uint8Array(pcm16.buffer);
            let binary = '';
            for (let i = 0; i < bytes.byteLength; i++) {
              binary += String.fromCharCode(bytes[i]);
            }
            const base64 = btoa(binary);

            ws.send(JSON.stringify({ audio: base64 }));
          };

          setStatus('connected');
        } catch (micErr: any) {
          console.error('[Mic capture error]', micErr);
          setStatus('error');
          setErrorMessage(`Microphone error: ${micErr.message || micErr}`);
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.error) {
            setErrorMessage(msg.error);
            setStatus('error');
            return;
          }
          if (msg.interrupted) {
            stopAudioPlayback();
            setStatus('connected');
            return;
          }
          if (msg.audio) {
            playPcmChunk(msg.audio);
          }
          if (msg.text) {
            setLiveCaption(prev => {
              const updated = prev + msg.text;
              return updated.length > 250 ? updated.slice(-250) : updated;
            });
          }
        } catch (msgErr) {
          console.warn('[WS message parse error]', msgErr);
        }
      };

      ws.onerror = (err) => {
        console.error('[Live WS Error]', err);
        setStatus('error');
        setErrorMessage('Failed to connect to Live Voice Server. Ensure server is running.');
      };

      ws.onclose = () => {
        console.log('[Live WS Closed]');
        if (status !== 'error') {
          setStatus('idle');
        }
      };
    } catch (e: any) {
      console.error('[Session start error]', e);
      setStatus('error');
      setErrorMessage(e.message || 'Could not start live voice session.');
    }
  };

  const endSession = () => {
    stopAudioPlayback();

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
    if (inputAudioCtxRef.current) {
      inputAudioCtxRef.current.close().catch(() => {});
      inputAudioCtxRef.current = null;
    }
    if (outputAudioCtxRef.current) {
      outputAudioCtxRef.current.close().catch(() => {});
      outputAudioCtxRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }
    setStatus('idle');
    setAudioLevel(0);
  };

  useEffect(() => {
    if (isOpen) {
      startSession();
    } else {
      endSession();
    }
    return () => {
      endSession();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-lg bg-[#0c0817] border border-purple-500/30 rounded-2xl shadow-[0_0_50px_rgba(168,85,247,0.2)] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-500/20 border border-purple-500/40 flex items-center justify-center text-purple-300 shadow-[0_0_15px_rgba(168,85,247,0.3)]">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-black text-white tracking-wide">Strike Tips Live Voice</h3>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  gemini-3.8-live
                </span>
              </div>
              <p className="text-xs text-slate-400">Bidirectional conversational racing AI</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close voice conversation"
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Visualizer */}
        <div className="p-8 flex flex-col items-center justify-center text-center space-y-6">
          {/* Wave ring */}
          <div className="relative w-36 h-36 flex items-center justify-center">
            <div
              className="absolute inset-0 rounded-full bg-purple-500/10 border border-purple-500/30 transition-all duration-150"
              style={{
                transform: `scale(${1 + (audioLevel / 100) * 0.4})`,
                opacity: status === 'speaking' ? 0.9 : 0.4,
              }}
            />
            <div
              className="absolute inset-2 rounded-full bg-indigo-500/20 border border-indigo-500/40 transition-all duration-100"
              style={{
                transform: `scale(${1 + (audioLevel / 100) * 0.2})`,
                opacity: status === 'speaking' ? 0.8 : 0.3,
              }}
            />
            <div className="relative z-10 w-24 h-24 rounded-full bg-gradient-to-br from-purple-600 to-indigo-700 flex items-center justify-center shadow-[0_0_30px_rgba(168,85,247,0.5)]">
              {status === 'speaking' ? (
                <Volume2 className="w-10 h-10 text-white animate-bounce" />
              ) : isMuted ? (
                <MicOff className="w-10 h-10 text-red-300" />
              ) : (
                <Mic className="w-10 h-10 text-white animate-pulse" />
              )}
            </div>
          </div>

          {/* Status Label */}
          <div>
            {status === 'connecting' && (
              <div className="flex items-center justify-center gap-2 text-sm text-yellow-400 font-semibold">
                <span className="w-2 h-2 rounded-full bg-yellow-400 animate-ping" />
                Connecting to Gemini Live...
              </div>
            )}
            {status === 'connected' && (
              <div className="flex items-center justify-center gap-2 text-sm text-emerald-400 font-semibold">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                {isMuted ? 'Muted — Tap Mic to speak' : 'Listening... speak naturally'}
              </div>
            )}
            {status === 'speaking' && (
              <div className="flex items-center justify-center gap-2 text-sm text-purple-300 font-semibold">
                <Sparkles className="w-4 h-4 text-purple-300 animate-spin" />
                Agent is speaking (Interrupt anytime)
              </div>
            )}
            {status === 'error' && (
              <div className="flex items-center justify-center gap-2 text-sm text-red-400 font-semibold max-w-sm">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{errorMessage || 'Voice connection failed'}</span>
              </div>
            )}
          </div>

          {/* Live Caption Text Box */}
          <div className="w-full bg-black/40 border border-white/10 rounded-xl p-4 min-h-[90px] max-h-[140px] overflow-y-auto text-left text-sm text-slate-300 leading-relaxed font-sans">
            {liveCaption ? (
              <p className="text-white">{liveCaption}</p>
            ) : (
              <p className="text-slate-500 italic text-center">
                Ask about today's races, course conditions, value picks, or exotics...
              </p>
            )}
          </div>

          {/* Controls */}
          <div className="flex items-center gap-4 w-full justify-center">
            <button
              onClick={() => setIsMuted(prev => !prev)}
              aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
              className={`p-3.5 rounded-xl border transition-all flex items-center justify-center gap-2 font-bold text-sm ${
                isMuted
                  ? 'bg-red-500/20 border-red-500/40 text-red-300'
                  : 'bg-white/10 border-white/20 text-white hover:bg-white/15'
              }`}
            >
              {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              {isMuted ? 'Unmute' : 'Mute'}
            </button>

            {status === 'speaking' && (
              <button
                onClick={stopAudioPlayback}
                className="p-3.5 rounded-xl border border-yellow-500/40 bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30 transition-all font-bold text-sm flex items-center gap-2"
              >
                Interrupt
              </button>
            )}

            {status === 'error' ? (
              <button
                onClick={startSession}
                className="px-5 py-3.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-sm transition-all shadow-[0_0_15px_rgba(168,85,247,0.3)]"
              >
                Retry
              </button>
            ) : (
              <button
                onClick={onClose}
                className="px-5 py-3.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-sm transition-all shadow-[0_0_15px_rgba(239,68,68,0.3)]"
              >
                End Call
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
