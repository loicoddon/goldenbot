'use client';

import { useEffect, useRef } from 'react';
import {
  ColorType,
  IChartApi,
  ISeriesApi,
  LineData,
  LineType,
  Time,
  createChart,
} from 'lightweight-charts';
import { apiGet } from '@/lib/api';
import { useGoldenSocket } from '@/lib/ws';

type HistoryRow = { timestamp: string; price: number };

// Rolling-average smoothing window (in ticks). Larger = rounder curve but
// slower reaction to actual price moves. 30 ticks ≈ 1 min at 2s polling.
const SMOOTH_WINDOW = 30;

/** Compute simple moving average over the input series. */
function smoothSMA(data: LineData[], window: number): LineData[] {
  if (data.length === 0 || window < 2) return data;
  const out: LineData[] = [];
  let sum = 0;
  const buf: number[] = [];
  for (const p of data) {
    const v = (p as any).value as number;
    buf.push(v);
    sum += v;
    if (buf.length > window) sum -= buf.shift() as number;
    out.push({ time: p.time, value: sum / buf.length });
  }
  return out;
}

export function PriceChart() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  // Sliding window of raw prices used to compute the live SMA value.
  const liveBufferRef = useRef<number[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#131826' },
        textColor: '#cbd5e1',
      },
      grid: {
        vertLines: { color: 'rgba(27, 34, 53, 0.3)' },
        horzLines: { color: 'rgba(27, 34, 53, 0.5)' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: 'rgba(27, 34, 53, 0.5)',
      },
      rightPriceScale: {
        borderColor: 'rgba(27, 34, 53, 0.5)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: 'rgba(255, 215, 0, 0.3)', labelBackgroundColor: '#B8860B' },
        horzLine: { color: 'rgba(255, 215, 0, 0.3)', labelBackgroundColor: '#B8860B' },
      },
    });
    const series = chart.addAreaSeries({
      lineColor: '#FFD700',
      topColor: 'rgba(255, 215, 0, 0.35)',
      bottomColor: 'rgba(255, 215, 0, 0.0)',
      lineWidth: 2,
      lineType: LineType.Curved,
      priceLineColor: 'rgba(255, 215, 0, 0.6)',
      priceLineStyle: 2,
      priceLineWidth: 1,
      crosshairMarkerBorderColor: '#FFD700',
      crosshairMarkerBackgroundColor: '#FFE066',
    });
    chartRef.current = chart;
    seriesRef.current = series;

    (async () => {
      try {
        const rows = await apiGet<HistoryRow[]>('/api/prices/history?minutes=120');
        const raw: LineData[] = rows.map((r) => ({
          time: (new Date(r.timestamp).getTime() / 1000) as Time,
          value: r.price,
        }));
        // Smooth the historical data so the chart loads in the same "look"
        // as the live updates that follow.
        const smoothed = smoothSMA(raw, SMOOTH_WINDOW);
        series.setData(smoothed);
        // Seed the live buffer with the tail of raw prices so the very next
        // live tick blends seamlessly with the historical SMA.
        liveBufferRef.current = rows
          .slice(-SMOOTH_WINDOW)
          .map((r) => r.price);
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
      const buf = liveBufferRef.current;
      buf.push(p.price);
      if (buf.length > SMOOTH_WINDOW) buf.shift();
      const sma = buf.reduce((s, v) => s + v, 0) / buf.length;
      seriesRef.current.update({
        time: (new Date(p.timestamp).getTime() / 1000) as Time,
        value: sma,
      });
    }
  });

  return (
    <div className="card h-[320px] md:h-[420px]">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm uppercase tracking-wider text-gray-400">XAU/USD</h2>
        <span className="text-[10px] md:text-xs text-gray-500">live · SMA{SMOOTH_WINDOW}</span>
      </div>
      <div ref={containerRef} className="w-full h-[260px] md:h-[360px]" />
    </div>
  );
}
