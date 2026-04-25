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
      className="p-6 h-full overflow-y-auto custom-scrollbar"
    >
      <div className="flex items-center justify-between max-w-4xl mx-auto w-full">
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
          onClick={saveSettings}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-500 text-white font-black hover:bg-purple-600 transition-all disabled:opacity-50 shadow-[0_0_20px_rgba(168,85,247,0.4)]"
        >
          {saved ? <span>✓ Saved</span> : <Save className="w-4 h-4" />}
          <span>{loading ? 'Saving...' : 'Save Protocol'}</span>
        </button>
      </div>

      <div className="grid gap-6 max-w-4xl mx-auto pb-12">
        {/* Bankroll Settings */}
        <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
            <DollarSign className="w-6 h-6 text-emerald-500" />
            <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Bankroll Protocol</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-3">
              <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">
                Starting Balance (ZAR)
              </label>
              <input
                type="number"
                value={settings.bankroll.startingBalance}
                onChange={e => handleChange('bankroll', 'startingBalance', parseFloat(e.target.value))}
                className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
            <div className="space-y-3">
              <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">
                Max Stake Per Race (%)
              </label>
              <input
                type="number"
                step="0.5"
                min="1"
                max="20"
                value={settings.bankroll.maxBetPercent}
                onChange={e => handleChange('bankroll', 'maxBetPercent', parseFloat(e.target.value))}
                className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
            <div className="space-y-3">
              <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">
                Daily Stop Loss (%)
              </label>
              <input
                type="number"
                step="1"
                min="5"
                max="50"
                value={settings.bankroll.dailyLossLimit}
                onChange={e => handleChange('bankroll', 'dailyLossLimit', parseFloat(e.target.value))}
                className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
            <div className="space-y-3">
              <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest block">
                Minimum Edge Req. (%)
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                max="20"
                value={settings.bankroll.minEdgeThreshold}
                onChange={e => handleChange('bankroll', 'minEdgeThreshold', parseFloat(e.target.value))}
                className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-purple-500/50 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* Alert Settings */}
        <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
            <Bell className="w-6 h-6 text-purple-500" />
            <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Notification Channels</h3>
          </div>
          
          <div className="space-y-4">
            {[
              { id: 'telegramEnabled', label: 'Telegram Dispatch', sub: 'Receive signals and alerts via encrypted bot channel' },
              { id: 'valueBetAlerts', label: 'Priority Edge Alerts', sub: 'High-priority notifications for edge > 15%' },
              { id: 'soundEnabled', label: 'HUD Audio Prompts', sub: 'Play synthesized interface sounds for critical events' },
            ].map((item) => (
              <div key={item.id} className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme group hover:bg-theme-secondary/50 transition-all">
                <div>
                  <div className="text-theme-primary font-black text-lg group-hover:text-purple-500 transition-colors">{item.label}</div>
                  <div className="text-xs text-theme-secondary font-bold mt-1">{item.sub}</div>
                </div>
                <button
                  onClick={() => handleChange('alerts', item.id, !settings.alerts[item.id as keyof typeof settings.alerts])}
                  className={`w-14 h-7 rounded-full transition-all relative ${settings.alerts[item.id as keyof typeof settings.alerts] ? 'bg-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.4)]' : 'bg-theme-secondary border border-theme'}`}
                >
                  <motion.div 
                    layout
                    className={`w-5 h-5 rounded-full bg-white absolute top-1 ${settings.alerts[item.id as keyof typeof settings.alerts] ? 'right-1' : 'left-1'}`} 
                  />
                </button>
              </div>
            ))}

            {settings.alerts.telegramEnabled && (
              <div className="pt-2">
                <button
                  onClick={testTelegram}
                  className="text-xs font-black text-purple-500 hover:text-purple-400 flex items-center gap-2 transition-colors uppercase tracking-widest"
                >
                  <RefreshCw className="w-4 h-4" />
                  Test Telegram Integration
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Scan Schedule */}
            <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
              <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
                <Clock className="w-6 h-6 text-amber-500" />
                <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Market Scans</h3>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest mb-3 block">
                    Daily Initialization Time
                  </label>
                  <input
                    type="time"
                    value={settings.schedule.scanTime}
                    onChange={e => handleChange('schedule', 'scanTime', e.target.value)}
                    className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black text-lg focus:outline-none focus:border-amber-500/50 transition-colors"
                  />
                </div>
                <div className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme">
                  <div>
                    <div className="text-theme-primary font-black uppercase text-sm">Autonomous Mode</div>
                    <div className="text-[10px] text-theme-secondary font-bold mt-1">Run without operator prompt</div>
                  </div>
                  <button
                    onClick={() => handleChange('schedule', 'autoScanEnabled', !settings.schedule.autoScanEnabled)}
                    className={`w-12 h-6 rounded-full transition-all relative ${settings.schedule.autoScanEnabled ? 'bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]' : 'bg-theme-secondary border border-theme'}`}
                  >
                    <motion.div 
                      layout
                      className={`w-4 h-4 rounded-full bg-white absolute top-1 ${settings.schedule.autoScanEnabled ? 'right-1' : 'left-1'}`} 
                    />
                  </button>
                </div>
              </div>
            </div>

            {/* AI Model Settings */}
            <div className="bg-theme-panel border border-theme rounded-3xl p-8 backdrop-blur-2xl">
              <div className="flex items-center gap-3 mb-8 pb-4 border-b border-theme">
                <Cpu className="w-6 h-6 text-blue-500" />
                <h3 className="text-xl font-black text-theme-primary tracking-tight uppercase">Inference Engine</h3>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="text-[10px] font-black text-theme-secondary uppercase tracking-widest mb-3 block">
                    Primary Router Model
                  </label>
                  <select
                    value={settings.ai.preferredModel}
                    onChange={e => handleChange('ai', 'preferredModel', e.target.value)}
                    className="w-full bg-theme-secondary/50 border border-theme rounded-2xl px-5 py-4 text-theme-primary font-black focus:outline-none focus:border-blue-500/50 transition-colors appearance-none"
                  >
                    <option value="groq-llama">Groq Cloud (Llama 3.3)</option>
                    <option value="ollama-racing">Ollama Local (Fast)</option>
                    <option value="ollama-ds">Ollama Local (DeepSeek)</option>
                    <option value="gemini">Gemini Pro</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-5 bg-theme-secondary/30 rounded-2xl border border-theme">
                  <div>
                    <div className="text-theme-primary font-black uppercase text-sm">Strict Local</div>
                    <div className="text-[10px] text-theme-secondary font-bold mt-1">Disable cloud fallback chain</div>
                  </div>
                  <button
                    onClick={() => handleChange('ai', 'localModelOnly', !settings.ai.localModelOnly)}
                    className={`w-12 h-6 rounded-full transition-all relative ${settings.ai.localModelOnly ? 'bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.4)]' : 'bg-theme-secondary border border-theme'}`}
                  >
                    <motion.div 
                      layout
                      className={`w-4 h-4 rounded-full bg-white absolute top-1 ${settings.ai.localModelOnly ? 'right-1' : 'left-1'}`} 
                    />
                  </button>
                </div>
              </div>
            </div>
        </div>
      </div>
    </motion.div>
  );
};
