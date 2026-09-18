import React, { useState } from 'react';
import {
  Volume2,
  VolumeX,
  Play,
  Pause,
  Download,
  Sparkles,
  Mic,
  Sliders,
  Check,
  AlertCircle,
  FileText,
  Zap,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useTTS } from '../hooks/useTTS';
import { GEMINI_VOICES, GROQ_VOICES } from '../lib/tts-api';

const PRESETS = [
  {
    label: 'Race Verdict',
    text: 'Race 7 at Kenilworth: Strong probability edge detected on runner number 4, Firealley. Current market odds offer outstanding value against the model consensus.',
  },
  {
    label: 'Market Mover',
    text: 'Noticeable market momentum at Greyville. Runner number 2 has contracted from 7.5 to 3.8 following heavy volume on the betting exchanges.',
  },
  {
    label: 'Bankroll Report',
    text: 'Bankroll Governor report: Total active balance is stable. Daily exposure remains strictly capped under five percent half-Kelly criteria with zero threshold breaches.',
  },
  {
    label: 'Turf Conditions',
    text: 'Durbanville going report: The turf is currently good to soft with a pen reading of twenty-four. Stalls positioned on the inside rail with clear weather forecast.',
  },
];

const GROQ_STYLES = [
  { id: 'cheerful', label: 'Cheerful', emoji: '🎉' },
  { id: 'dramatic', label: 'Dramatic', emoji: '🎭' },
  { id: 'whisper', label: 'Whisper', emoji: '🤫' },
  { id: 'calm', label: 'Calm', emoji: '🌿' },
  { id: 'urgent', label: 'Urgent', emoji: '⚡' },
];

export const TextToSpeechView: React.FC = () => {
  const tts = useTTS();
  const [inputText, setInputText] = useState(PRESETS[0].text);
  const [selectedStyle, setSelectedStyle] = useState<string>('');

  const handleSynthesize = async () => {
    if (!inputText.trim()) return;
    await tts.speak(inputText, {
      provider: tts.provider,
      voice: tts.voiceId,
      style: tts.provider === 'groq' ? selectedStyle : undefined,
    });
  };

  const handleDownload = () => {
    if (!tts.currentAudioUrl) return;
    const a = document.createElement('a');
    a.href = tts.currentAudioUrl;
    a.download = `strike-tips-speech-${tts.provider}-${tts.voiceId}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const currentVoiceList = tts.provider === 'groq' ? GROQ_VOICES : GEMINI_VOICES;

  return (
    <div className="flex-1 flex flex-col p-4 md:p-8 max-w-6xl mx-auto w-full gap-6 text-slate-100">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <Volume2 className="w-7 h-7 text-purple-400" />
              Natural Text to Speech
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-purple-500/20 border border-purple-500/30 text-purple-300 text-[11px] font-bold">
              24kHz HD Neural
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Convert racing verdicts, bankroll reports, and custom notes into human-quality voice using Google Gemini TTS and Groq Speech.
          </p>
        </div>

        {/* Live Provider Status */}
        <div className="flex items-center gap-2 bg-black/40 border border-white/10 p-1.5 rounded-xl">
          <button
            onClick={() => tts.setProvider('gemini')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              tts.provider === 'gemini'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Gemini TTS
          </button>
          <button
            onClick={() => tts.setProvider('groq')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              tts.provider === 'groq'
                ? 'bg-amber-600 text-white shadow-lg shadow-amber-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            Groq Speech
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Input & Presets (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="bg-[#0f0b1e]/80 border border-white/10 rounded-2xl p-5 backdrop-blur-xl shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-purple-400" />
                Text to Synthesize
              </span>
              <span className="text-[11px] text-slate-500 font-mono">
                {inputText.length} chars · {inputText.split(/\s+/).filter(Boolean).length} words
              </span>
            </div>

            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Type or paste any text to convert to natural human-sounding speech…"
              rows={6}
              className="w-full bg-black/40 border border-white/10 rounded-xl p-3.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none font-sans leading-relaxed"
            />

            {/* Quick Preset Buttons */}
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Quick Racing Presets
              </span>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setInputText(p.text)}
                    className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-300 hover:text-white transition-all text-left"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Groq Vocal Style Modifiers (only for Groq) */}
            {tts.provider === 'groq' && (
              <div className="flex flex-col gap-1.5 pt-2 border-t border-white/10">
                <span className="text-[11px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1">
                  <Sliders className="w-3.5 h-3.5" />
                  Groq Orpheus Vocal Direction
                </span>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setSelectedStyle('')}
                    className={`px-2.5 py-1 rounded-lg text-xs transition-all ${
                      selectedStyle === ''
                        ? 'bg-amber-500 text-black font-bold'
                        : 'bg-white/5 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    Natural (Default)
                  </button>
                  {GROQ_STYLES.map((st) => (
                    <button
                      key={st.id}
                      onClick={() => setSelectedStyle(st.id)}
                      className={`px-2.5 py-1 rounded-lg text-xs transition-all flex items-center gap-1 ${
                        selectedStyle === st.id
                          ? 'bg-amber-500 text-black font-bold'
                          : 'bg-white/5 text-slate-300 hover:bg-white/10'
                      }`}
                    >
                      <span>{st.emoji}</span>
                      <span>{st.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-2">
                {tts.speaking ? (
                  <button
                    onClick={tts.stop}
                    className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-sm flex items-center gap-2 transition-all shadow-lg shadow-red-600/30"
                  >
                    <VolumeX className="w-4 h-4" />
                    Stop Speech
                  </button>
                ) : (
                  <button
                    onClick={() => void handleSynthesize()}
                    disabled={tts.busy || !inputText.trim()}
                    className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm flex items-center gap-2 transition-all shadow-lg shadow-purple-600/30 disabled:opacity-50"
                  >
                    {tts.busy ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Synthesizing…
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 fill-white" />
                        Convert & Speak
                      </>
                    )}
                  </button>
                )}

                {tts.speaking && (
                  <button
                    onClick={tts.paused ? tts.resume : tts.pause}
                    className="px-3.5 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white text-sm font-semibold transition-all"
                  >
                    {tts.paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                  </button>
                )}
              </div>

              {tts.currentAudioUrl && (
                <button
                  onClick={handleDownload}
                  title="Download WAV file"
                  className="px-3.5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-1.5 transition-all"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download WAV
                </button>
              )}
            </div>

            {/* Error / Denial note */}
            {tts.deniedReason && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{tts.deniedReason}</span>
              </div>
            )}
          </div>

          {/* Active Audio Waveform Card */}
          {tts.speaking && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#0f0b1e]/80 border border-purple-500/30 rounded-2xl p-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 h-6">
                  {[40, 75, 55, 90, 65, 80, 45, 95, 70, 50, 85, 60].map((h, i) => (
                    <motion.div
                      key={i}
                      animate={{ height: ['20%', `${h}%`, '30%'] }}
                      transition={{
                        repeat: Infinity,
                        duration: 0.6 + (i % 4) * 0.15,
                        ease: 'easeInOut',
                      }}
                      className="w-1 bg-gradient-to-t from-purple-500 to-indigo-400 rounded-full"
                    />
                  ))}
                </div>
                <div>
                  <p className="text-xs font-bold text-white">Playing Voice</p>
                  <p className="text-[11px] text-purple-300">
                    {tts.currentVoice.name} ({tts.provider.toUpperCase()}) · {tts.playbackRate}x speed
                  </p>
                </div>
              </div>

              {/* Speed Switcher */}
              <div className="flex items-center gap-1 bg-black/40 p-1 rounded-lg border border-white/10 text-xs">
                {[0.75, 1.0, 1.25, 1.5].map((speed) => (
                  <button
                    key={speed}
                    onClick={() => tts.setPlaybackRate(speed)}
                    className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                      tts.playbackRate === speed ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {speed}x
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </div>

        {/* Right Column: Voice Persona Selector (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="bg-[#0f0b1e]/80 border border-white/10 rounded-2xl p-5 backdrop-blur-xl shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <Mic className="w-4 h-4 text-purple-400" />
                Select Voice Persona
              </span>
              <span className="text-[11px] text-purple-400 font-bold uppercase tracking-wider">
                {tts.provider === 'gemini' ? 'Gemini 3.1 Neural' : 'Groq Orpheus'}
              </span>
            </div>

            {/* Voice Cards */}
            <div className="flex flex-col gap-2.5">
              {currentVoiceList.map((v) => {
                const isSelected = tts.voiceId === v.id;
                return (
                  <div
                    key={v.id}
                    onClick={() => tts.setVoiceId(v.id)}
                    className={`cursor-pointer p-3 rounded-xl border transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-purple-950/40 border-purple-500 shadow-md shadow-purple-500/10'
                        : 'bg-black/20 border-white/5 hover:border-white/20 hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs ${
                          isSelected ? 'bg-purple-600 text-white' : 'bg-white/10 text-slate-400'
                        }`}
                      >
                        {v.name.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white">{v.name}</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-white/10 text-slate-300 font-medium">
                            {v.gender}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 leading-snug">{v.description}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-purple-600 flex items-center justify-center text-white">
                          <Check className="w-3 h-3" />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Engine Overview Specs */}
            <div className="pt-3 border-t border-white/10 flex flex-col gap-2 text-xs text-slate-400">
              <div className="flex items-center justify-between">
                <span>Active Model</span>
                <span className="text-white font-mono text-[11px]">
                  {tts.provider === 'gemini' ? 'gemini-3.1-flash-tts-preview' : 'canopylabs/orpheus-v1-english'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Output Format</span>
                <span className="text-white font-semibold">24kHz 16-bit Mono WAV</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Download Footprint</span>
                <span className="text-emerald-400 font-semibold">0 MB (Zero local weights needed)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
