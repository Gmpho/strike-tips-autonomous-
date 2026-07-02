import React, { useState, useEffect } from 'react';
import { Save, Bell, Clock, Cpu, DollarSign, RefreshCw, Settings as SettingsIcon, FlaskConical, Zap, Smartphone } from 'lucide-react';
import { motion } from 'framer-motion';
import { apiFetch } from '../../lib/api-fetch';
import { initAudio, playAlertTone, playValueBetTone } from '../../engine/audio';
import { checkWebGPUSupport, getStorageEstimate, clearWebLLMStorage, StorageEstimateInfo } from '../../lib/webllm';
import { usePWA } from '../../hooks/usePWA';

interface Settings {
  bankroll: { startingBalance: number; maxBetPercent: number; dailyLossLimit: number; minEdgeThreshold: number };
  alerts: { telegramEnabled: boolean; soundEnabled: boolean; valueBetAlerts: boolean };
  schedule: { scanTime: string; autoScanEnabled: boolean };
  ai: { preferredModel: string; localModelOnly: boolean };
  paper: { paperMode: boolean; paperBalance: number };
  autonomous: { autoBetEnabled: boolean; autoBetMinEdge: number };
}

const DEFAULTS: Settings = {
  bankroll: { startingBalance: 1000.0, maxBetPercent: 5.0, dailyLossLimit: 20.0, minEdgeThreshold: 5.0 },
  alerts: { telegramEnabled: true, soundEnabled: false, valueBetAlerts: true },
  schedule: { scanTime: '11:00', autoScanEnabled: true },
  ai: { preferredModel: 'groq-llama', localModelOnly: false },
  paper: { paperMode: false, paperBalance: 1000.0 },
  autonomous: { autoBetEnabled: false, autoBetMinEdge: 8.0 },
};

export const SettingsView: React.FC = () => {
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'ok' | 'err'>('idle');
  const [webGpuSupported, setWebGpuSupported] = useState(false);
  const [storageEstimate, setStorageEstimate] = useState<StorageEstimateInfo | null>(null);
  const [clearingStorage, setClearingStorage] = useState(false);
  const [clearingSwCache, setClearingSwCache] = useState(false);
  const { isInstallable, isInstalled, installPWA } = usePWA();

  const loadStorageInfo = () => {
    getStorageEstimate().then(est => setStorageEstimate(est));
  };

  useEffect(() => {
    checkWebGPUSupport().then(supported => setWebGpuSupported(supported));
    loadStorageInfo();
  }, []);

  const clearSwCache = async () => {
    if (!window.confirm("Clear the service worker cache? This will free up storage but may slow the first page load after clearing.")) return;
    setClearingSwCache(true);
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
      if ((navigator as any).serviceWorker?.controller) {
        (navigator as any).serviceWorker.controller.postMessage({ type: 'CLEAR_CACHE' });
      }
      loadStorageInfo();
    } catch {
      alert("Failed to clear SW cache. Try reopening the app.");
    } finally {
      setClearingSwCache(false);
    }
  };

  const handleResetStorage = async () => {
    if (!window.confirm("Are you sure you want to delete all cached WebGPU model files? You will need to redownload them when starting a local browser session.")) {
      return;
    }
    setClearingStorage(true);
    try {
      const success = await clearWebLLMStorage();
      if (success) {
        alert("WebGPU Local Storage successfully reset!");
      } else {
        alert("Reset completed (storage was already empty).");
      }
      loadStorageInfo();
    } catch (e: any) {
      alert("Failed to reset WebGPU storage: " + (e.message || e));
    } finally {
      setClearingStorage(false);
    }
  };

  // Load persisted settings from backend on mount
  useEffect(() => {
    apiFetch('/api/config')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        setSettings({
          bankroll: {
            startingBalance: data.bankroll?.total_bankroll ?? DEFAULTS.bankroll.startingBalance,
            maxBetPercent: data.bankroll?.max_bet_percent ?? DEFAULTS.bankroll.maxBetPercent,
            dailyLossLimit: data.bankroll?.daily_loss_limit ?? DEFAULTS.bankroll.dailyLossLimit,
            minEdgeThreshold: data.bankroll?.min_edge_threshold ?? DEFAULTS.bankroll.minEdgeThreshold,
          },
          alerts: {
            telegramEnabled: data.telegramEnabled ?? DEFAULTS.alerts.telegramEnabled,
            soundEnabled: data.soundEnabled ?? DEFAULTS.alerts.soundEnabled,
            valueBetAlerts: data.valueBetAlerts ?? DEFAULTS.alerts.valueBetAlerts,
          },
          schedule: {
            scanTime: data.scanTime ?? DEFAULTS.schedule.scanTime,
            autoScanEnabled: data.autoScanEnabled ?? DEFAULTS.schedule.autoScanEnabled,
          },
          ai: {
            preferredModel: data.preferredModel ?? DEFAULTS.ai.preferredModel,
            localModelOnly: data.localModelOnly ?? DEFAULTS.ai.localModelOnly,
          },
          paper: {
            paperMode: data.paper_mode ?? DEFAULTS.paper.paperMode,
            paperBalance: data.paper_balance ?? DEFAULTS.paper.paperBalance,
          },
          autonomous: {
            autoBetEnabled: data.auto_bet_enabled ?? DEFAULTS.autonomous.autoBetEnabled,
            autoBetMinEdge: data.auto_bet_min_edge ?? DEFAULTS.autonomous.autoBetMinEdge,
          },
        });
        localStorage.setItem('strike_sound_enabled', String(data.soundEnabled ?? DEFAULTS.alerts.soundEnabled));
        localStorage.setItem('strike_value_bet_alerts', String(data.valueBetAlerts ?? DEFAULTS.alerts.valueBetAlerts));
      })
      .catch(() => {/* keep defaults */});
  }, []);

  const set = (section: keyof Settings, key: string, value: unknown) =>
    setSettings(prev => ({ ...prev, [section]: { ...prev[section], [key]: value } }));

  const save = async () => {
    setSaveState('saving');
    try {
      const res = await apiFetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...settings.bankroll,
          ...settings.alerts,
          ...settings.schedule,
          ...settings.ai,
          paper_mode: settings.paper.paperMode,
          paper_balance: settings.paper.paperBalance,
          auto_bet_enabled: settings.autonomous.autoBetEnabled,
          auto_bet_min_edge: settings.autonomous.autoBetMinEdge,
        }),
      });
      if (res.ok) {
        setSaveState('ok');
        localStorage.setItem('strike_sound_enabled', String(settings.alerts.soundEnabled));
        localStorage.setItem('strike_value_bet_alerts', String(settings.alerts.valueBetAlerts));
      } else {
        setSaveState('err');
      }
    } catch {
      setSaveState('err');
    }
    setTimeout(() => setSaveState('idle'), 2500);
  };

  const testTelegram = async () => {
    try {
      await apiFetch('/api/config/test_telegram', { method: 'POST' });
      alert('Test message sent! Check your Telegram.');
    } catch {
      alert('Failed to send test message');
    }
  };

  const Toggle = ({ on, onToggle, color }: { on: boolean; onToggle: () => void; color: string }) => (
    <button
      onClick={onToggle}
      className={`w-12 h-6 rounded-full transition-all relative flex-shrink-0 ${on ? color : 'bg-theme-secondary border border-theme'}`}
    >
      <motion.div layout className={`w-4 h-4 rounded-full bg-white absolute top-1 ${on ? 'right-1' : 'left-1'}`} />
    </button>
  );

  const saveLabel = { idle: 'Save Protocol', saving: 'Saving...', ok: '✓ Saved', err: '✗ Failed' }[saveState];
  const saveCls = saveState === 'err' ? 'bg-red-500 hover:bg-red-600' : saveState === 'ok' ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-purple-500 hover:bg-purple-600';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="p-6 h-full overflow-y-auto custom-scrollbar"
    >
      {/* Header */}
      <div className="flex items-center justify-between max-w-4xl mx-auto w-full mb-6">
        <div>
          <h2 className="text-2xl font-bold bg-linear-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent flex items-center gap-3">
            <SettingsIcon className="w-6 h-6 text-purple-500" />
            System Configuration
          </h2>
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
            Governance & Logic Parameters
          </p>
        </div>
        <button
          onClick={save}
          disabled={saveState === 'saving'}
          className={`flex items-center gap-2 px-6 py-3 rounded-xl text-white font-black transition-all disabled:opacity-50 shadow-[0_0_20px_rgba(168,85,247,0.4)] ${saveCls}`}
        >
          <Save className="w-4 h-4" />
          <span>{saveLabel}</span>
        </button>
      </div>

      <div className="grid gap-6 max-w-4xl mx-auto pb-12">

        {/* Bankroll */}
        <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
            <DollarSign className="w-6 h-6 text-emerald-500" />
            <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Bankroll Protocol</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {([
              { label: 'Starting Balance (ZAR)', key: 'startingBalance' },
              { label: 'Max Stake Per Race (%)', key: 'maxBetPercent', step: 0.5, min: 1, max: 20 },
              { label: 'Daily Stop Loss (%)', key: 'dailyLossLimit', step: 1, min: 5, max: 50 },
              { label: 'Minimum Edge Req. (%)', key: 'minEdgeThreshold', step: 0.5, min: 0, max: 20 },
            ] as const).map(({ label, key, ...rest }) => (
              <div key={key} className="space-y-3">
                <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">{label}</label>
                <input
                  type="number"
                  {...rest}
                  value={settings.bankroll[key]}
                  onChange={e => set('bankroll', key, parseFloat(e.target.value))}
                  className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
            <Bell className="w-6 h-6 text-purple-500" />
            <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Notification Channels</h3>
          </div>
          <div className="space-y-4">
            {([
              { id: 'telegramEnabled', label: 'Telegram Dispatch', sub: 'Receive signals and alerts via encrypted bot channel' },
              { id: 'valueBetAlerts', label: 'Priority Edge Alerts', sub: 'High-priority notifications for edge > 15%' },
              { id: 'soundEnabled', label: 'HUD Audio Prompts', sub: 'Play synthesized interface sounds for critical events' },
            ] as const).map(item => (
              <div key={item.id} className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme group hover:bg-theme-secondary/50 transition-all">
                <div>
                  <div className="text-theme-primary font-black text-lg group-hover:text-purple-500 transition-colors">{item.label}</div>
                  <div className="text-xs text-theme-secondary font-bold mt-1">{item.sub}</div>
                </div>
                <Toggle
                  on={settings.alerts[item.id]}
                  onToggle={() => {
                    const newVal = !settings.alerts[item.id];
                    set('alerts', item.id, newVal);
                    if (item.id === 'soundEnabled') {
                      localStorage.setItem('strike_sound_enabled', String(newVal));
                      if (newVal) {
                        initAudio();
                        playAlertTone();
                      }
                    } else if (item.id === 'valueBetAlerts') {
                      localStorage.setItem('strike_value_bet_alerts', String(newVal));
                      if (newVal) {
                        initAudio();
                        playValueBetTone();
                      }
                    }
                  }}
                  color="bg-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.4)]"
                />
              </div>
            ))}
            {settings.alerts.telegramEnabled && (
              <div className="pt-2">
                <button onClick={testTelegram} className="text-xs font-black text-purple-500 hover:text-purple-400 flex items-center gap-2 transition-colors uppercase tracking-widest">
                  <RefreshCw className="w-4 h-4" />
                  Test Telegram Integration
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Schedule + AI */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
            <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
              <Clock className="w-6 h-6 text-amber-500" />
              <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Market Scans</h3>
            </div>
            <div className="space-y-6">
              <div>
                <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest mb-3 block">Daily Initialization Time</label>
                <input
                  type="time"
                  value={settings.schedule.scanTime}
                  onChange={e => set('schedule', 'scanTime', e.target.value)}
                  className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-amber-500/50 transition-colors"
                />
              </div>
              <div className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme">
                <div>
                  <div className="text-theme-primary font-black uppercase text-sm">Autonomous Mode</div>
                  <div className="text-[10px] text-theme-secondary font-bold mt-1">Run without operator prompt</div>
                </div>
                <Toggle on={settings.schedule.autoScanEnabled} onToggle={() => set('schedule', 'autoScanEnabled', !settings.schedule.autoScanEnabled)} color="bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]" />
              </div>
            </div>
          </div>

          <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
            <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
              <Cpu className="w-6 h-6 text-blue-500" />
              <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Inference Engine</h3>
            </div>
            <div className="space-y-6">
              <div>
                <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest mb-3 block">Primary Router Model</label>
                <select
                  value={settings.ai.preferredModel}
                  onChange={e => set('ai', 'preferredModel', e.target.value)}
                  className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black focus:outline-none focus:border-blue-500/50 transition-colors appearance-none"
                >
                  <optgroup label="☁️ Cloud">
                    <option value="groq-llama">Groq Cloud (Llama 3.3)</option>
                    <option value="gemini">Gemini Flash</option>
                  </optgroup>
                  <optgroup label="🌐 Browser Local (WebGPU)">
                    <option value="webllm-qwen-0.5b" disabled={!webGpuSupported}>
                      Qwen 2.5 0.5B {!webGpuSupported ? '(No WebGPU)' : '⚡'}
                    </option>
                    <option value="webllm-llama-1b" disabled={!webGpuSupported}>
                      Llama 3.2 1B {!webGpuSupported ? '(No WebGPU)' : '⚡'}
                    </option>
                    <option value="webllm-qwen-1.5b" disabled={!webGpuSupported}>
                      Qwen 2.5 1.5B {!webGpuSupported ? '(No WebGPU)' : '⚡'}
                    </option>
                  </optgroup>
                </select>
              </div>

              {/* Storage estimate gauge */}
              {storageEstimate && storageEstimate.isSupported && (
                <div className="p-5 bg-theme-secondary/20 rounded-2xl border border-theme text-xs space-y-3">
                  <div className="flex justify-between font-black text-theme-primary uppercase text-[10px] tracking-wider">
                    <span>Browser Storage Quota</span>
                    <span className={storageEstimate.percentage > 80 ? "text-rose-400 font-black animate-pulse" : "text-blue-400"}>
                      {storageEstimate.percentage}% ({Math.round(storageEstimate.usage / (1024 * 1024))} MB used)
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden border border-white/5">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${storageEstimate.percentage > 80 ? "bg-rose-500" : "bg-blue-500"}`} 
                      style={{ width: `${storageEstimate.percentage}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[9px] text-theme-secondary font-bold">
                    <span>Free space: {Math.round(storageEstimate.free / (1024 * 1024))} MB</span>
                    <span>Qwen 1.5B requires ~1.1 GB</span>
                  </div>
                </div>
              )}

              {/* PWA App Installation */}
              {isInstallable && (
                <div className="flex items-center justify-between p-5 bg-purple-950/20 rounded-2xl border border-purple-500/20">
                  <div>
                    <div className="text-purple-300 font-black uppercase text-sm flex items-center gap-2">
                      <Smartphone className="w-4.5 h-4.5 text-purple-400" />
                      <span>Install Strike Tips PWA</span>
                    </div>
                    <div className="text-[10px] text-slate-400 font-bold mt-1">Run as a standalone app with offline WebGPU support</div>
                  </div>
                  <button
                    onClick={installPWA}
                    className="bg-purple-900/60 hover:bg-purple-800 border border-purple-500/30 text-purple-200 px-4 py-2 rounded-xl text-xs font-black uppercase transition-all shrink-0 min-h-[36px]"
                  >
                    Install
                  </button>
                </div>
              )}

              {isInstalled && (
                <div className="flex items-center justify-between p-5 bg-emerald-950/20 rounded-2xl border border-emerald-500/20">
                  <div>
                    <div className="text-emerald-300 font-black uppercase text-sm flex items-center gap-2">
                      <Smartphone className="w-4.5 h-4.5 text-emerald-400" />
                      <span>App Installed Successfully</span>
                    </div>
                    <div className="text-[10px] text-slate-400 font-bold mt-1">Standalone mode active (PWA offline caching enabled)</div>
                  </div>
                  <div className="text-emerald-400 text-xs font-black uppercase border border-emerald-500/30 px-3 py-1 rounded-lg bg-emerald-500/10">Active</div>
                </div>
              )}

              {/* Clear SW Cache Button */}
              <div className="flex items-center justify-between p-5 bg-amber-950/20 rounded-2xl border border-amber-500/20">
                <div>
                  <div className="text-amber-300 font-black uppercase text-sm">Clear App Cache</div>
                  <div className="text-[10px] text-slate-500 font-bold mt-1">Free up space by purging cached static assets (SW cache)</div>
                </div>
                <button
                  onClick={clearSwCache}
                  disabled={clearingSwCache}
                  className="bg-amber-900/60 hover:bg-amber-800 border border-amber-500/30 text-amber-200 px-4 py-2 rounded-xl text-xs font-black uppercase transition-all shrink-0 min-h-[36px] disabled:opacity-50"
                >
                  {clearingSwCache ? "Clearing..." : "Clear Cache"}
                </button>
              </div>

              {/* Reset Storage Button */}
              <div className="flex items-center justify-between p-5 bg-rose-950/20 rounded-2xl border border-rose-500/20">
                <div>
                  <div className="text-rose-300 font-black uppercase text-sm">Reset Browser AI Storage</div>
                  <div className="text-[10px] text-slate-500 font-bold mt-1">Purge cached weights to resolve download glitches</div>
                </div>
                <button
                  onClick={handleResetStorage}
                  disabled={clearingStorage}
                  className="bg-rose-900/60 hover:bg-rose-800 border border-rose-500/30 text-rose-200 px-4 py-2 rounded-xl text-xs font-black uppercase transition-all shrink-0 min-h-[36px] disabled:opacity-50"
                >
                  {clearingStorage ? "Resetting..." : "Reset"}
                </button>
              </div>

              <div className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme">
                <div>
                  <div className="text-theme-primary font-black uppercase text-sm">Strict Local</div>
                  <div className="text-[10px] text-theme-secondary font-bold mt-1">Disable cloud fallback chain</div>
                </div>
                <Toggle on={settings.ai.localModelOnly} onToggle={() => set('ai', 'localModelOnly', !settings.ai.localModelOnly)} color="bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.4)]" />
              </div>
            </div>
          </div>
        </div>

        {/* Paper Trading + Auto Bet */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
            <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
              <FlaskConical className="w-6 h-6 text-cyan-500" />
              <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Paper Trading</h3>
            </div>
            <div className="space-y-6">
              <div className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme">
                <div>
                  <div className="text-theme-primary font-black uppercase text-sm">Virtual Mode</div>
                  <div className="text-[10px] text-theme-secondary font-bold mt-1">Use virtual money — no real stakes</div>
                </div>
                <Toggle on={settings.paper.paperMode} onToggle={() => set('paper', 'paperMode', !settings.paper.paperMode)} color="bg-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.4)]" />
              </div>
              {settings.paper.paperMode && (
                <div className="space-y-3">
                  <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">Virtual Balance (ZAR)</label>
                  <input
                    type="number"
                    value={settings.paper.paperBalance}
                    onChange={e => set('paper', 'paperBalance', parseFloat(e.target.value))}
                    className="w-full bg-theme-secondary/50 border border-cyan-500/30 rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-cyan-500/50 transition-colors"
                  />
                </div>
              )}
            </div>
          </div>

          <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
            <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
              <Zap className="w-6 h-6 text-yellow-500" />
              <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Auto Bet</h3>
            </div>
            <div className="space-y-6">
              <div className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme">
                <div>
                  <div className="text-theme-primary font-black uppercase text-sm">Autonomous Betting</div>
                  <div className="text-[10px] text-theme-secondary font-bold mt-1">Agent places bets automatically on value alerts</div>
                </div>
                <Toggle on={settings.autonomous.autoBetEnabled} onToggle={() => set('autonomous', 'autoBetEnabled', !settings.autonomous.autoBetEnabled)} color="bg-yellow-500 shadow-[0_0_15px_rgba(234,179,8,0.4)]" />
              </div>
              {settings.autonomous.autoBetEnabled && (
                <div className="space-y-3">
                  <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">Min Edge to Auto-Bet (%)</label>
                  <input
                    type="number"
                    step={0.5}
                    min={5}
                    max={30}
                    value={settings.autonomous.autoBetMinEdge}
                    onChange={e => set('autonomous', 'autoBetMinEdge', parseFloat(e.target.value))}
                    className="w-full bg-theme-secondary/50 border border-yellow-500/30 rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-yellow-500/50 transition-colors"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </motion.div>
  );
};
