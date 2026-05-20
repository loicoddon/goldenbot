'use client';

import { useEffect, useRef } from 'react';
import {
  ColorType,
  IChartApi,
  ISeriesApi,
  LineData,
  Time,
  createChart,
} from 'lightweight-charts';
import { apiGet } from '@/lib/api';
import { useGoldenSocket } from '@/lib/ws';

type HistoryRow = { timestamp: string; price: number };

export function PriceChart() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#131826' },
        textColor: '#cbd5e1',
      },
      grid: {
        vertLines: { color: '#1B2235' },
        horzLines: { color: '#1B2235' },
      },
      timeScale: { timeVisible: true, secondsVisible: true },
      rightPriceScale: { borderColor: '#1B2235' },
    });
    const series = chart.addLineSeries({ color: '#FFD700', lineWidth: 2 });
    chartRef.current = chart;
    seriesRef.current = series;

    (async () => {
      try {
        const rows = await apiGet<HistoryRow[]>('/api/prices/history?minutes=120');
        const data: LineData[] = rows.map((r) => ({
          time: (new Date(r.timestamp).getTime() / 1000) as Time,
          value: r.price,
        }));
        series.setData(data);
        chart.timeScale().fitContent();
      } catch {
        /* ignore */
      }
    })();

    const resize = () => chart.applyOptions({ autoSize: true });
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('resize', resize);
      chart.remove();
    };
  }, []);

  useGoldenSocket((msg) => {
    if (msg.channel === 'goldenbot:price' && seriesRef.current) {
      const p = msg.data;
      seriesRef.current.update({
        time: (new Date(p.timestamp).getTime() / 1000) as Time,
        value: p.price,
      });
    }
  });

  return (
    <div className="card h-[320px] md:h-[420px]">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm uppercase tracking-wider text-gray-400">XAU/USD</h2>
        <span className="text-[10px] md:text-xs text-gray-500">live</span>
      </div>
      <div ref={containerRef} className="w-full h-[260px] md:h-[360px]" />
    </div>
  );
}
