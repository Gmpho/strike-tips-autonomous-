let ctx: AudioContext | null = null;

function getCtx(): AudioContext {
  if (!ctx) ctx = new AudioContext();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

export function isSoundEnabled(): boolean {
  try {
    return localStorage.getItem('strike_sound_enabled') === 'true';
  } catch {
    return false;
  }
}

export function initAudio(): void {
  try {
    if (!ctx) ctx = new AudioContext();
    if (ctx.state === 'suspended') {
      ctx.resume();
    }
  } catch (e) {
    console.warn('AudioContext failed to initialize:', e);
  }
}

// Automatically resume AudioContext upon first user interaction if sound is enabled
if (typeof window !== 'undefined') {
  const resumeOnInteraction = () => {
    if (isSoundEnabled()) {
      initAudio();
    }
    window.removeEventListener('click', resumeOnInteraction);
    window.removeEventListener('touchstart', resumeOnInteraction);
    window.removeEventListener('keydown', resumeOnInteraction);
  };
  window.addEventListener('click', resumeOnInteraction);
  window.addEventListener('touchstart', resumeOnInteraction);
  window.addEventListener('keydown', resumeOnInteraction);
}

export function playAlertTone(): void {
  if (!isSoundEnabled()) return
  try {
    const ac = getCtx()
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, ac.currentTime)
    osc.frequency.exponentialRampToValueAtTime(1320, ac.currentTime + 0.1)
    gain.gain.setValueAtTime(0.15, ac.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.3)
    osc.connect(gain).connect(ac.destination)
    osc.start()
    osc.stop(ac.currentTime + 0.3)
  } catch {}
}

export function playValueBetTone(): void {
  if (!isSoundEnabled()) return
  try {
    const ac = getCtx()
    const now = ac.currentTime
    const notes = [660, 880, 1100]
    notes.forEach((freq, i) => {
      const osc = ac.createOscillator()
      const gain = ac.createGain()
      osc.type = 'triangle'
      osc.frequency.setValueAtTime(freq, now + i * 0.15)
      gain.gain.setValueAtTime(0.12, now + i * 0.15)
      gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.15 + 0.25)
      osc.connect(gain).connect(ac.destination)
      osc.start(now + i * 0.15)
      osc.stop(now + i * 0.15 + 0.25)
    })
  } catch {}
}

export function playSettleTone(won: boolean): void {
  if (!isSoundEnabled()) return
  try {
    const ac = getCtx()
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.type = won ? 'sine' : 'sawtooth'
    if (won) {
      osc.frequency.setValueAtTime(660, ac.currentTime)
      osc.frequency.exponentialRampToValueAtTime(1320, ac.currentTime + 0.2)
    } else {
      osc.frequency.setValueAtTime(440, ac.currentTime)
      osc.frequency.exponentialRampToValueAtTime(220, ac.currentTime + 0.3)
    }
    gain.gain.setValueAtTime(0.12, ac.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.4)
    osc.connect(gain).connect(ac.destination)
    osc.start()
    osc.stop(ac.currentTime + 0.4)
  } catch {}
}
