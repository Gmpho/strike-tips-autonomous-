// Native ApexCharts wrapper (no react-apexcharts: avoids React 19 peer
// risk). Tree-shaken: only the chart types imported here ship in the lazy
// analytics chunk.
import React, { useEffect, useRef } from 'react';
import ApexCharts from 'apexcharts/core';
import 'apexcharts/area';
import 'apexcharts/bar';
import 'apexcharts/column';
import 'apexcharts/donut';
import 'apexcharts/heatmap';
import 'apexcharts/line';
import 'apexcharts/rangeArea';
import type { ApexOptions } from 'apexcharts';

interface ApexChartProps {
  type: 'area' | 'bar' | 'column' | 'donut' | 'heatmap' | 'line' | 'rangeArea';
  series: ApexOptions['series'];
  options: ApexOptions;
  height?: number | string;
}

export const ApexChart: React.FC<ApexChartProps> = React.memo(
  ({ type, series, options, height = 280 }) => {
    const elRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<ApexCharts | null>(null);
    const optsRef = useRef({ type, series, options });
    optsRef.current = { type, series, options };

    useEffect(() => {
      if (!elRef.current) return;
      const { type: t, series: s, options: o } = optsRef.current;
      const chart = new ApexCharts(elRef.current, {
        ...o,
        chart: { ...(o.chart || {}), type: t as never, height },
        series: s,
      });
      chartRef.current = chart;
      void chart.render();
      return () => {
        void chartRef.current?.destroy();
        chartRef.current = null;
      };
      // Mount once; updates flow through the effect below.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
      void chartRef.current?.updateOptions(
        {
          ...options,
          chart: { ...(options.chart || {}), type: type as never, height },
          series,
        },
        true,
        true,
      );
    }, [type, series, options, height]);

    return <div ref={elRef} className="w-full" />;
  },
);
ApexChart.displayName = 'ApexChart';
