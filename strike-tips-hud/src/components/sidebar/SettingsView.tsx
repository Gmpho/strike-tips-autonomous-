import React, { useState } from 'react';
import { Save, Bell, Clock, Cpu, DollarSign, RefreshCw, Settings as SettingsIcon } from 'lucide-react';
import { motion } from 'framer-motion';

interface Settings {
  bankroll: {
    startingBalance: number;
    maxBetPercent: number;
    dailyLossLimit: number;
    minEdgeThreshold: number;
  };
  alerts: {
    telegramEnabled: boolean;
    soundEnabled: boolean;
    valueBetAlerts: boolean;
  };
  schedule: {
    scanTime: string;
    autoScanEnabled: boolean;
  };
  ai: {
    preferredModel: string;
    localModelOnly: boolean;
  };
  display: {
    theme: 'dark' | 'light' | 'system';
    fontSize: number;
  };
}

export const SettingsView: React.FC = () => {
  const [settings, setSettings] = useState<Settings>({
    bankroll: {
      startingBalance: 2500.5,
      maxBetPercent: 5.0,
      dailyLossLimit: 20.0,
      minEdgeThreshold: 5.0
    },
    alerts: {
      telegramEnabled: true,
      soundEnabled: false,
      valueBetAlerts: true
    },
    schedule: {
      scanTime: '11:00',
      autoScanEnabled: true
    },
    ai: {
      preferredModel: 'groq-llama',
      localModelOnly: false
    },
    display: {
      theme: 'dark',
      fontSize: 16
    }
  });

  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChange = (section: keyof Settings, key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
    setSaved(false);
  };

  const saveSettings = async () => {
    setLoading(true);
    try {
      // Call API to save settings
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const testTelegram = async () => {
    try {
      await fetch('/api/config/test_telegram', { method: 'POST' });
      alert('Test message sent! Check your Telegram.');
    } catch (err) {
      alert('Failed to send test message');
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="p-8 h-full overflow-y-auto custom-scrollbar"
    >
      <div className="flex items-center justify-between mb-8 max-w-4xl mx-auto">
        <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
          <SettingsIcon className="w-6 h-6 text-purple-500" />
          System Configuration
        </h2>
        <button
          onClick={saveSettings}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-500 text-white font-bold hover:bg-purple-600 transition-all disabled:opacity-50 shadow-[0_0_20px_rgba(168,85,247,0.4)] hover:shadow-[0_0_30px_rgba(168,85,247,0.6)]"
        >
          {saved ? <span className="text-emerald-300">✓ Saved</span> : <Save className="w-4 h-4" />}
          Save Changes
        </button>
      </div>

      <div className="grid gap-6 max-w-4xl mx-auto pb-12">
        {/* Bankroll Settings */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-white/10">
            <DollarSign className="w-6 h-6 text-emerald-400" />
            <h3 className="text-xl font-bold text-white tracking-tight">Bankroll Protocol</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3 block">
                Starting Balance (ZAR)
              </label>
              <input
                type="number"
                value={settings.bankroll.startingBalance}
                onChange={e => handleChange('bankroll', 'startingBalance', parseFloat(e.target.value))}
                className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white font-mono text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3 block">
                Max Stake Per Race (%)
              </label>
              <input
                type="number"
                step="0.5"
                min="1"
                max="20"
                value={settings.bankroll.maxBetPercent}
                onChange={e => handleChange('bankroll', 'maxBetPercent', parseFloat(e.target.value))}
                className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white font-mono text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3 block">
                Daily Stop Loss (%)
              </label>
              <input
                type="number"
                step="1"
                min="5"
                max="50"
                value={settings.bankroll.dailyLossLimit}
                onChange={e => handleChange('bankroll', 'dailyLossLimit', parseFloat(e.target.value))}
                className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white font-mono text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3 block">
                Minimum Edge Req. (%)
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                max="20"
                value={settings.bankroll.minEdgeThreshold}
                onChange={e => handleChange('bankroll', 'minEdgeThreshold', parseFloat(e.target.value))}
                className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white font-mono text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
          </div>
        </motion.div>

        {/* Alert Settings */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-white/10">
            <Bell className="w-6 h-6 text-purple-400" />
            <h3 className="text-xl font-bold text-white tracking-tight">Notification Channels</h3>
          </div>
          
          <div className="space-y-6">
            <div className="flex items-center justify-between p-4 bg-black/20 rounded-2xl border border-white/5 hover:bg-black/40 transition-colors">
              <div>
                <div className="text-white font-bold text-lg">Telegram Dispatch</div>
                <div className="text-sm text-slate-500 mt-1">Receive signals and alerts via Telegram bot</div>
              </div>
              <button
                onClick={() => handleChange('alerts', 'telegramEnabled', !settings.alerts.telegramEnabled)}
                className={`w-16 h-8 rounded-full transition-colors relative ${settings.alerts.telegramEnabled ? 'bg-purple-500' : 'bg-white/10'}`}
              >
                <motion.div 
                  layout
                  className={`w-6 h-6 rounded-full bg-white absolute top-1 ${settings.alerts.telegramEnabled ? 'right-1' : 'left-1'}`} 
                />
              </button>
            </div>

            <div className="flex items-center justify-between p-4 bg-black/20 rounded-2xl border border-white/5 hover:bg-black/40 transition-colors">
              <div>
                <div className="text-white font-bold text-lg">Value Bet Priority Alerts</div>
                <div className="text-sm text-slate-500 mt-1">High-priority notifications for edge &gt; 15%</div>
              </div>
              <button
                onClick={() => handleChange('alerts', 'valueBetAlerts', !settings.alerts.valueBetAlerts)}
                className={`w-16 h-8 rounded-full transition-colors relative ${settings.alerts.valueBetAlerts ? 'bg-purple-500' : 'bg-white/10'}`}
              >
                <motion.div 
                  layout
                  className={`w-6 h-6 rounded-full bg-white absolute top-1 ${settings.alerts.valueBetAlerts ? 'right-1' : 'left-1'}`} 
                />
              </button>
            </div>

            <div className="flex items-center justify-between p-4 bg-black/20 rounded-2xl border border-white/5 hover:bg-black/40 transition-colors">
              <div>
                <div className="text-white font-bold text-lg">HUD Audio Prompts</div>
                <div className="text-sm text-slate-500 mt-1">Play interface sounds for critical events</div>
              </div>
              <button
                onClick={() => handleChange('alerts', 'soundEnabled', !settings.alerts.soundEnabled)}
                className={`w-16 h-8 rounded-full transition-colors relative ${settings.alerts.soundEnabled ? 'bg-purple-500' : 'bg-white/10'}`}
              >
                <motion.div 
                  layout
                  className={`w-6 h-6 rounded-full bg-white absolute top-1 ${settings.alerts.soundEnabled ? 'right-1' : 'left-1'}`} 
                />
              </button>
            </div>

            {settings.alerts.telegramEnabled && (
              <div className="pt-2 pl-4">
                <button
                  onClick={testTelegram}
                  className="text-sm font-bold text-purple-400 hover:text-purple-300 flex items-center gap-2 transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  Test Telegram Integration
                </button>
              </div>
            )}
          </div>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Scan Schedule */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
            >
              <div className="flex items-center gap-3 mb-8 pb-4 border-b border-white/10">
                <Clock className="w-6 h-6 text-amber-400" />
                <h3 className="text-xl font-bold text-white tracking-tight">Market Scans</h3>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3 block">
                    Daily Initialization Time
                  </label>
                  <input
                    type="time"
                    value={settings.schedule.scanTime}
                    onChange={e => handleChange('schedule', 'scanTime', e.target.value)}
                    className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white font-mono text-lg focus:outline-none focus:border-amber-500/50 transition-colors"
                  />
                </div>
                <div className="flex items-center justify-between p-4 bg-black/20 rounded-2xl border border-white/5">
                  <div>
                    <div className="text-white font-bold">Autonomous</div>
                    <div className="text-xs text-slate-500 mt-1">Run without prompt</div>
                  </div>
                  <button
                    onClick={() => handleChange('schedule', 'autoScanEnabled', !settings.schedule.autoScanEnabled)}
                    className={`w-14 h-7 rounded-full transition-colors relative ${settings.schedule.autoScanEnabled ? 'bg-amber-500' : 'bg-white/10'}`}
                  >
                    <motion.div 
                      layout
                      className={`w-5 h-5 rounded-full bg-white absolute top-1 ${settings.schedule.autoScanEnabled ? 'right-1' : 'left-1'}`} 
                    />
                  </button>
                </div>
              </div>
            </motion.div>

            {/* AI Model Settings */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
            >
              <div className="flex items-center gap-3 mb-8 pb-4 border-b border-white/10">
                <Cpu className="w-6 h-6 text-blue-400" />
                <h3 className="text-xl font-bold text-white tracking-tight">Inference Engine</h3>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="text-xs font-black text-slate-500 uppercase tracking-widest mb-3 block">
                    Primary Router Model
                  </label>
                  <select
                    value={settings.ai.preferredModel}
                    onChange={e => handleChange('ai', 'preferredModel', e.target.value)}
                    className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white font-bold focus:outline-none focus:border-blue-500/50 transition-colors appearance-none"
                  >
                    <option value="groq-llama">Groq Cloud (Llama 3.3)</option>
                    <option value="ollama-racing">Ollama Local (Fast)</option>
                    <option value="ollama-ds">Ollama Local (DeepSeek)</option>
                    <option value="gemini">Gemini Pro</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-4 bg-black/20 rounded-2xl border border-white/5">
                  <div>
                    <div className="text-white font-bold">Strict Local</div>
                    <div className="text-xs text-slate-500 mt-1">Disable cloud fallback</div>
                  </div>
                  <button
                    onClick={() => handleChange('ai', 'localModelOnly', !settings.ai.localModelOnly)}
                    className={`w-14 h-7 rounded-full transition-colors relative ${settings.ai.localModelOnly ? 'bg-blue-500' : 'bg-white/10'}`}
                  >
                    <motion.div 
                      layout
                      className={`w-5 h-5 rounded-full bg-white absolute top-1 ${settings.ai.localModelOnly ? 'right-1' : 'left-1'}`} 
                    />
                  </button>
                </div>
              </div>
            </motion.div>
        </div>
      </div>
    </motion.div>
  );
};