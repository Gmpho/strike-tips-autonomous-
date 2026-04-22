import React, { useState, useEffect } from 'react';
import { Sun, Moon } from 'lucide-react';

type Theme = 'dark' | 'light';

export const ThemeToggle: React.FC = () => {
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    const saved = localStorage.getItem('strike-theme') as Theme;
    if (saved) {
      setTheme(saved);
      applyTheme(saved);
    }
  }, []);

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('strike-theme', next);
    applyTheme(next);
  };

  const applyTheme = (t: Theme) => {
    if (t === 'light') {
      document.documentElement.classList.add('light');
    } else {
      document.documentElement.classList.remove('light');
    }
  };

  return (
    <button
      onClick={toggle}
      className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-all"
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? (
        <Sun className="w-4 h-4 text-amber-400" />
      ) : (
        <Moon className="w-4 h-4 text-purple-400" />
      )}
    </button>
  );
};