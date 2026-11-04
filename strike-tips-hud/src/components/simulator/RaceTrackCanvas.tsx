import React, { useRef, useEffect } from 'react';
import type { SimulatedRunner, SimulationFrame } from '../../engine/simulation/pacingEngine';
import { FINISH_LINE_X } from '../../engine/simulation/pacingEngine';

interface RaceTrackCanvasProps {
  simRunners: SimulatedRunner[];
  frame: SimulationFrame | null;
  highlightValueBet: boolean;
  onHorseClick?: (runner: SimulatedRunner) => void;
}

export const RaceTrackCanvas: React.FC<RaceTrackCanvasProps> = ({
  simRunners,
  frame,
  highlightValueBet,
  onHorseClick,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Fixed virtual canvas resolution
    const V_WIDTH = 1000;
    const V_HEIGHT = 400;

    // Handle high DPI displays
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    ctx.save();
    ctx.scale((rect.width * dpr) / V_WIDTH, (rect.height * dpr) / V_HEIGHT);

    // 1. Draw Turf Surface with mowing patterns
    const grassGrad = ctx.createLinearGradient(0, 0, 0, V_HEIGHT);
    grassGrad.addColorStop(0, '#15803D'); // Darker top turf
    grassGrad.addColorStop(0.5, '#16A34A');
    grassGrad.addColorStop(1, '#22C55E');
    ctx.fillStyle = grassGrad;
    ctx.fillRect(0, 0, V_WIDTH, V_HEIGHT);

    // Alternating lawn stripes
    ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
    for (let y = 60; y < V_HEIGHT; y += 40) {
      ctx.fillRect(0, y, V_WIDTH, 20);
    }

    // 2. Top Billboard / Rail with Sponsor Logos (like the LuckyFish/Tote broadcast)
    const bannerHeight = 44;
    ctx.fillStyle = '#09090B';
    ctx.fillRect(0, 0, V_WIDTH, bannerHeight);

    const sponsors = [
      { bg: '#EC4899', text: 'LUCKYFISH', textColor: '#FFFFFF' },
      { bg: '#18181B', text: 'TOTE', textColor: '#FFFFFF' },
      { bg: '#8B5CF6', text: 'STRIKE TIPS', textColor: '#FFFFFF' },
      { bg: '#0284C7', text: '4RACING', textColor: '#FFFFFF' },
      { bg: '#EC4899', text: 'LUCKYFISH', textColor: '#FFFFFF' },
      { bg: '#18181B', text: 'TOTE', textColor: '#FFFFFF' },
      { bg: '#8B5CF6', text: 'STRIKE TIPS', textColor: '#FFFFFF' },
      { bg: '#059669', text: 'HOLLYWOODBETS', textColor: '#FFFFFF' },
    ];

    const panelWidth = V_WIDTH / sponsors.length;
    sponsors.forEach((sp, idx) => {
      ctx.fillStyle = sp.bg;
      ctx.fillRect(idx * panelWidth + 2, 4, panelWidth - 4, bannerHeight - 8);
      ctx.fillStyle = sp.textColor;
      ctx.font = 'bold 11px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(sp.text, idx * panelWidth + panelWidth / 2, bannerHeight / 2);
    });

    // Rail post line
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, bannerHeight);
    ctx.lineTo(V_WIDTH, bannerHeight);
    ctx.stroke();

    for (let x = 0; x < V_WIDTH; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, bannerHeight);
      ctx.lineTo(x, bannerHeight + 12);
      ctx.stroke();
    }

    // 3. Distance Markers
    const markers = [
      { x: 300, label: '300m' },
      { x: 500, label: '200m' },
      { x: 700, label: '100m' },
      { x: 780, label: '50m' },
    ];

    markers.forEach((m) => {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(m.x, bannerHeight);
      ctx.lineTo(m.x, V_HEIGHT - 20);
      ctx.stroke();
      ctx.setLineDash([]);

      // Top distance flag
      ctx.fillStyle = 'rgba(24, 24, 27, 0.85)';
      ctx.fillRect(m.x - 18, bannerHeight + 6, 36, 16);
      ctx.fillStyle = '#F4F4F5';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(m.label, m.x, bannerHeight + 18);
    });

    // 4. Red Finish Line & Post
    ctx.strokeStyle = '#EF4444';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(FINISH_LINE_X, bannerHeight);
    ctx.lineTo(FINISH_LINE_X, V_HEIGHT - 10);
    ctx.stroke();

    // Finish post indicator
    ctx.fillStyle = '#EF4444';
    ctx.fillRect(FINISH_LINE_X - 6, bannerHeight + 2, 12, 18);
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 9px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('FIN', FINISH_LINE_X, bannerHeight + 15);

    // 5. Draw Horses & Jockeys
    if (frame && frame.runners) {
      // Sort by Y so horses in lower lanes appear in front of top lanes
      const sortedRunners = [...frame.runners].sort((a, b) => a.y - b.y);

      sortedRunners.forEach((rp) => {
        const runnerMeta = simRunners.find((r) => r.id === rp.id);
        if (!runnerMeta) return;

        const x = rp.x;
        const y = rp.y;
        const isVal = runnerMeta.isAiValue;
        const phase = rp.stridePhase; // 0 to 1

        // Highlight AI Value Bet with vibrant aura
        if (isVal && highlightValueBet) {
          ctx.save();
          ctx.shadowColor = '#A855F7';
          ctx.shadowBlur = 18;
          ctx.strokeStyle = '#C084FC';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.ellipse(x + 10, y + 10, 36, 20, 0, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();

          // Value Badge
          ctx.fillStyle = '#9333EA';
          ctx.fillRect(x - 2, y - 26, 28, 12);
          ctx.fillStyle = '#FFFFFF';
          ctx.font = 'bold 8px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('VALUE', x + 12, y - 17);
        }

        // Draw Horse Body (Equine silhouette with galloping legs)
        ctx.save();
        ctx.translate(x, y);

        // Natural coat shades: bay, chestnut, black
        const coatColor = parseInt(runnerMeta.number, 10) % 2 === 0 ? '#451A03' : '#78350F';
        ctx.fillStyle = coatColor;

        // Galloping leg calculation:
        // phase 0.0 - 0.5: legs reaching forward / back
        // phase 0.5 - 1.0: legs tucked / gathering
        const legReach = Math.sin(phase * Math.PI * 2);

        // Hind Legs
        ctx.strokeStyle = coatColor;
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(2, 8);
        ctx.lineTo(-10 - legReach * 8, 18 - Math.abs(legReach) * 4);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(6, 8);
        ctx.lineTo(-4 - legReach * 6, 20);
        ctx.stroke();

        // Fore Legs
        ctx.beginPath();
        ctx.moveTo(26, 8);
        ctx.lineTo(34 + legReach * 8, 18);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(22, 8);
        ctx.lineTo(28 + legReach * 6, 20);
        ctx.stroke();

        // Horse Torso (Oval)
        ctx.beginPath();
        ctx.ellipse(16, 6, 16, 8, 0, 0, Math.PI * 2);
        ctx.fill();

        // Horse Neck & Head
        ctx.beginPath();
        ctx.moveTo(26, 4);
        ctx.lineTo(36, -4);
        ctx.lineTo(40, -2);
        ctx.lineTo(32, 8);
        ctx.closePath();
        ctx.fill();

        // Muzzle & Ears
        ctx.beginPath();
        ctx.arc(38, -3, 3, 0, Math.PI * 2);
        ctx.fill();

        // Tail
        ctx.strokeStyle = '#18181B';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(2, 4);
        ctx.quadraticCurveTo(-6, 2, -12, 10 + Math.sin(phase * Math.PI * 4) * 3);
        ctx.stroke();

        // Saddlecloth
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(10, 1, 12, 9);
        ctx.fillStyle = '#09090B';
        ctx.font = 'bold 8px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(runnerMeta.number, 16, 8);

        // Jockey Silks (Jersey)
        ctx.fillStyle = runnerMeta.silkColor;
        ctx.beginPath();
        ctx.ellipse(14, -3, 6, 5, -0.4, 0, Math.PI * 2);
        ctx.fill();

        // Jockey Helmet / Cap
        ctx.fillStyle = runnerMeta.capColor;
        ctx.beginPath();
        ctx.arc(17, -9, 4, 0, Math.PI * 2);
        ctx.fill();

        // Cloth / Runner Tag Floating Above
        ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
        ctx.fillRect(2, -22, 28, 11);
        ctx.fillStyle = '#F4F4F5';
        ctx.font = 'bold 8px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`#${runnerMeta.number}`, 16, -14);

        ctx.restore();
      });
    }

    // 6. Bottom Running Rail
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, V_HEIGHT - 8);
    ctx.lineTo(V_WIDTH, V_HEIGHT - 8);
    ctx.stroke();

    for (let x = 0; x < V_WIDTH; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, V_HEIGHT - 8);
      ctx.lineTo(x, V_HEIGHT);
      ctx.stroke();
    }

    ctx.restore();
  }, [simRunners, frame, highlightValueBet]);

  return (
    <div className="w-full relative overflow-hidden rounded-xl bg-black border border-theme shadow-2xl">
      <canvas
        ref={canvasRef}
        className="w-full h-auto block aspect-[5/2] cursor-pointer"
        style={{ touchAction: 'none' }}
        onClick={(e) => {
          if (!onHorseClick || !frame || !canvasRef.current) return;
          const rect = canvasRef.current.getBoundingClientRect();
          const clickX = ((e.clientX - rect.left) / rect.width) * 1000;
          const clickY = ((e.clientY - rect.top) / rect.height) * 400;

          // Find closest horse
          let closest = null;
          let minDist = 40;
          frame.runners.forEach((rp) => {
            const dist = Math.hypot(rp.x - clickX, rp.y - clickY);
            if (dist < minDist) {
              minDist = dist;
              closest = simRunners.find((r) => r.id === rp.id);
            }
          });
          if (closest) onHorseClick(closest);
        }}
      />
    </div>
  );
};
