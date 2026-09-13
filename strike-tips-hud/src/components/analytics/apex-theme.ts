// Shared ApexCharts theme: HUD dark glass. Import once per chart file.
import type { ApexOptions, ApexYAxis } from 'apexcharts';

export const APEX_FORE = '#94a3b8';
export const APEX_GRID = 'rgba(148,163,184,0.12)';
export const APEX_UP = '#10b981';
export const APEX_DOWN = '#ef4444';
export const APEX_ACCENT = '#a855f7';
export const APEX_FONT = "Inter, ui-sans-serif, system-ui, sans-serif";

export const apexBase: ApexOptions = {
  chart: {
    background: 'transparent',
    foreColor: APEX_FORE,
    fontFamily: APEX_FONT,
    toolbar: { show: false },
    zoom: { enabled: false },
    animations: { enabled: true, speed: 600 },
  },
  grid: {
    borderColor: APEX_GRID,
    strokeDashArray: 4,
    padding: { left: 8, right: 8 },
    xaxis: { lines: { show: false } },
  },
  tooltip: {
    theme: 'dark',
    style: { fontSize: '12px', fontFamily: APEX_FONT },
  },
  legend: {
    labels: { colors: APEX_FORE },
    fontFamily: APEX_FONT,
  },
  dataLabels: { enabled: false },
};

export function randAxis(decimals = 0): ApexYAxis {
  return {
    labels: {
      formatter: (v: number) => {
        const a = Math.abs(v);
        if (a >= 1000) return `R${(v / 1000).toFixed(1)}k`;
        return `R${v.toFixed(decimals)}`;
      },
    },
  };
}
