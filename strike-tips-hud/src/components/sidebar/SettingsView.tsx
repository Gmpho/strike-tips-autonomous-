import React, { useState } from 'react';
import { Save, Bell, Clock, Cpu, DollarSign, Palette, RefreshCw } from 'lucide-react';

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
    <div className="p-8 animate-in fade-in duration-500 max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-black text-white tracking-tight">System Settings</h2>
        <button
          onClick={saveSettings}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 rounded-xl bg-purple-500 text-white font-bold hover:bg-purple-600 transition-all disabled:opacity-50"
        >
          {saved ? <span className="text-emerald-300">✓ Saved</span> : <Save className="w-4 h-4" />}
          Save Changes
        </button>
      </div>

      <div className="grid gap-6">
        {/* Bankroll Settings */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            <h3 className="text-lg font-bold text-white">Bankroll Configuration</h3>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Starting Balance (R)
              </label>
              <input
                type="number"
                value={settings.bankroll.startingBalance}
                onChange={e => handleChange('bankroll', 'startingBalance', parseFloat(e.target.value))}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Max Bet (%)
              </label>
              <input
                type="number"
                step="0.5"
                min="1"
                max="20"
                value={settings.bankroll.maxBetPercent}
                onChange={e => handleChange('bankroll', 'maxBetPercent', parseFloat(e.target.value))}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Daily Loss Limit (%)
              </label>
              <input
                type="number"
                step="1"
                min="5"
                max="50"
                value={settings.bankroll.dailyLossLimit}
                onChange={e => handleChange('bankroll', 'dailyLossLimit', parseFloat(e.target.value))}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Min Edge Threshold (%)
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                max="20"
                value={settings.bankroll.minEdgeThreshold}
                onChange={e => handleChange('bankroll', 'minEdgeThreshold', parseFloat(e.target.value))}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white font-mono"
              />
            </div>
          </div>
        </div>

        {/* Alert Settings */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <Bell className="w-5 h-5 text-purple-400" />
            <h3 className="text-lg font-bold text-white">Alert Preferences</h3>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium">Telegram Notifications</div>
                <div className="text-xs text-slate-500">Receive tips and alerts via Telegram</div>
              </div>
              <button
                onClick={() => handleChange('alerts', 'telegramEnabled', !settings.alerts.telegramEnabled)}
                className={`w-14 h-7 rounded-full transition-colors ${settings.alerts.telegramEnabled ? 'bg-emerald-500' : 'bg-white/10'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.alerts.telegramEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium">Value Bet Alerts</div>
                <div className="text-xs text-slate-500">Notify when strong value bets are detected</div>
              </div>
              <button
                onClick={() => handleChange('alerts', 'valueBetAlerts', !settings.alerts.valueBetAlerts)}
                className={`w-14 h-7 rounded-full transition-colors ${settings.alerts.valueBetAlerts ? 'bg-emerald-500' : 'bg-white/10'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.alerts.valueBetAlerts ? 'translate-x-8' : 'translate-x-1'}`} />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium">Sound Effects</div>
                <div className="text-xs text-slate-500">Play sounds for important events</div>
              </div>
              <button
                onClick={() => handleChange('alerts', 'soundEnabled', !settings.alerts.soundEnabled)}
                className={`w-14 h-7 rounded-full transition-colors ${settings.alerts.soundEnabled ? 'bg-emerald-500' : 'bg-white/10'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.alerts.soundEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
              </button>
            </div>

            {settings.alerts.telegramEnabled && (
              <button
                onClick={testTelegram}
                className="mt-4 text-sm text-purple-400 hover:text-purple-300 flex items-center gap-2"
              >
                <RefreshCw className="w-3 h-3" />
                Test Telegram Connection
              </button>
            )}
          </div>
        </div>

        {/* Scan Schedule */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <Clock className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-bold text-white">Scan Schedule</h3>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Daily Scan Time
              </label>
              <input
                type="time"
                value={settings.schedule.scanTime}
                onChange={e => handleChange('schedule', 'scanTime', e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white font-mono"
              />
            </div>
            <div className="flex items-center justify-between px-4 py-3">
              <div>
                <div className="text-white font-medium">Auto-Scan</div>
                <div className="text-xs text-slate-500">Run daily scan automatically</div>
              </div>
              <button
                onClick={() => handleChange('schedule', 'autoScanEnabled', !settings.schedule.autoScanEnabled)}
                className={`w-14 h-7 rounded-full transition-colors ${settings.schedule.autoScanEnabled ? 'bg-emerald-500' : 'bg-white/10'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.schedule.autoScanEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
              </button>
            </div>
          </div>
        </div>

        {/* AI Model Settings */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <Cpu className="w-5 h-5 text-blue-400" />
            <h3 className="text-lg font-bold text-white">AI Model Configuration</h3>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Preferred Model
              </label>
              <select
                value={settings.ai.preferredModel}
                onChange={e => handleChange('ai', 'preferredModel', e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white"
              >
                <option value="groq-llama">Groq - Llama 3.3 (Fast)</option>
                <option value="ollama-racing">Local - Racing Llama</option>
                <option value="ollama-ds">Local - DS Racing (Deep Analysis)</option>
                <option value="gemini">Gemini Flash</option>
              </select>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium">Local Model Only</div>
                <div className="text-xs text-slate-500">Never send data to cloud providers</div>
              </div>
              <button
                onClick={() => handleChange('ai', 'localModelOnly', !settings.ai.localModelOnly)}
                className={`w-14 h-7 rounded-full transition-colors ${settings.ai.localModelOnly ? 'bg-emerald-500' : 'bg-white/10'}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.ai.localModelOnly ? 'translate-x-8' : 'translate-x-1'}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Display Settings */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <Palette className="w-5 h-5 text-pink-400" />
            <h3 className="text-lg font-bold text-white">Display Settings</h3>
          </div>
          
          <div className="space-y-6">
            <div>
              <label className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 block">
                Font Size: {settings.display.fontSize}px
              </label>
              <input
                type="range"
                min="12"
                max="20"
                value={settings.display.fontSize}
                onChange={e => {
                  const size = parseInt(e.target.value);
                  handleChange('display', 'fontSize', size);
                  document.documentElement.style.fontSize = `${size}px`;
                }}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-slate-600 mt-1">
                <span>Small</span>
                <span>Default</span>
                <span>Large</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};