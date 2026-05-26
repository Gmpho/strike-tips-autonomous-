let ctx: AudioContext | null = null

function getCtx(): AudioContext {
  if (!ctx) ctx = new AudioContext()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

export function isSoundEnabled(): boolean {
  try {
    const raw = localStorage.getItem('strike_hud_state')
    if (!raw) return false
    const state = JSON.parse(raw)
    return state?.soundEnabled ?? false
  } catch {
    return false
  }
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
