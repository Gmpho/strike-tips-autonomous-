import React from 'react';

/**
 * One punter's public avatar.
 *
 * The backend decides the mode (`google` | `preset` | `initials`) because the
 * leaderboard is public: a player who does not want their Google photo on a
 * public board can switch to a preset or plain initials (see
 * POST /api/league/me/avatar). Anything we cannot render falls back to
 * initials derived from the handle, so a row never shows a broken image.
 */
export interface AvatarDescriptor {
  mode?: 'google' | 'preset' | 'initials' | string | null;
  url?: string | null;
  preset?: string | null;
  emoji?: string | null;
  gradient?: string | null;
}

/**
 * Preset styling lives in the frontend on purpose: Tailwind only compiles
 * class names it can see in source. A gradient string built in Python at
 * runtime would never make it into the CSS bundle.
 */
export const PRESET_STYLES: Record<string, { emoji: string; cls: string; label: string }> = {
  jockey: { emoji: '🏇', cls: 'from-amber-500 to-orange-600', label: 'Jockey' },
  trophy: { emoji: '🏆', cls: 'from-yellow-400 to-amber-600', label: 'Trophy' },
  comet: { emoji: '☄️', cls: 'from-indigo-500 to-purple-600', label: 'Comet' },
  bolt: { emoji: '⚡', cls: 'from-cyan-400 to-blue-600', label: 'Bolt' },
  fox: { emoji: '🦊', cls: 'from-orange-400 to-rose-500', label: 'Fox' },
  eagle: { emoji: '🦅', cls: 'from-slate-500 to-slate-700', label: 'Eagle' },
  shark: { emoji: '🦈', cls: 'from-teal-400 to-cyan-700', label: 'Shark' },
  crown: { emoji: '👑', cls: 'from-fuchsia-500 to-purple-700', label: 'Crown' },
};

export function initialsOf(name?: string | null): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

type Mode = 'google' | 'preset' | 'initials';

function resolveMode(avatar?: AvatarDescriptor | null): Mode {
  if (!avatar) return 'initials';
  if (avatar.mode === 'google' && avatar.url) return 'google';
  if (avatar.mode === 'preset' && (PRESET_STYLES[avatar.preset || ''] || avatar.emoji)) return 'preset';
  return 'initials';
}

interface AvatarProps {
  avatar?: AvatarDescriptor | null;
  name?: string | null;
  /** Pixel diameter. Defaults to 32. */
  size?: number;
  /** Extra classes for the wrapper (ring, margin, etc). */
  className?: string;
  /** Render the initials at a smaller ratio (useful for 3-letter handles). */
  title?: string;
}

export const Avatar: React.FC<AvatarProps> = ({ avatar, name, size = 32, className = '', title }) => {
  // Google photos can be blocked or rot; remember which URL failed so we fall
  // back to initials instead of leaving a broken-image glyph on the board.
  const [brokenUrl, setBrokenUrl] = React.useState<string | null>(null);
  const rawMode = resolveMode(avatar);
  const mode: Mode = rawMode === 'google' && brokenUrl === avatar?.url ? 'initials' : rawMode;
  const style: React.CSSProperties = { width: size, height: size, fontSize: Math.round(size * 0.4) };
  const label = title || name || 'Punter';

  if (mode === 'google') {
    return (
      <img
        src={avatar!.url as string}
        alt={label}
        title={label}
        style={style}
        referrerPolicy="no-referrer"
        loading="lazy"
        className={`rounded-full object-cover bg-slate-700 flex-shrink-0 ${className}`}
        onError={() => setBrokenUrl(avatar!.url ?? null)}
      />
    );
  }

  if (mode === 'preset') {
    const preset = avatar!.preset ? PRESET_STYLES[avatar!.preset] : undefined;
    const emoji = preset?.emoji || avatar!.emoji || '🏇';
    const cls = preset?.cls || 'from-slate-600 to-slate-800';
    return (
      <span
        role="img"
        aria-label={preset?.label || 'Avatar'}
        title={label}
        style={style}
        className={`rounded-full bg-gradient-to-br ${cls} flex items-center justify-center flex-shrink-0 select-none ${className}`}
      >
        <span style={{ fontSize: Math.round(size * 0.52), lineHeight: 1 }}>{emoji}</span>
      </span>
    );
  }

  return (
    <span
      aria-hidden="true"
      title={label}
      style={style}
      className={`rounded-full bg-slate-700 text-slate-200 font-bold flex items-center justify-center flex-shrink-0 select-none ${className}`}
    >
      {initialsOf(name)}
    </span>
  );
};

export default Avatar;
