'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ColorType,
  IChartApi,
  ISeriesApi,
  LineData,
  Time,
  createChart,
} from 'lightweight-charts';
import { useRef } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '@/lib/api';

type BacktestStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

type BacktestSummary = {
  id: number;
  symbol: string;
  strategy: string;
  timeframe: string;
  status: BacktestStatus;
  final_equity: number | null;
  total_return_pct: number | null;
  sharpe: number | null;
  profit_factor: number | null;
  max_drawdown_pct: number | null;
  winrate: number | null;
  total_trades: number | null;
  from_ts: string;
  to_ts: string;
  started_at: string;
  finished_at: string | null;
};

type EquityPoint = { ts: string; equity: number; balance: number };
type TradeRow = {
  side: string;
  entry: number;
  exit: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  close_reason: string | null;
  opened_at: string | null;
  closed_at: string | null;
};

type BacktestDetail = BacktestSummary & {
  error: string | null;
  trades: TradeRow[] | null;
  equity_curve: EquityPoint[] | null;
  initial_capital: number;
  leverage: number;
  risk_per_trade_pct: number;
  expectancy: number | null;
};

const todayIso = () => new Date().toISOString().slice(0, 16);
const daysAgoIso = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 16);
};

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<string[]>([]);
  const [form, setForm] = useState({
    strategy: 'ema_crossover',
    timeframe: '1m',
    initial_capital: 1000,
    leverage: 500,
    risk_per_trade_pct: 1.0,
    from_ts: daysAgoIso(2),
    to_ts: todayIso(),
  });
  const [runs, setRuns] = useState<BacktestSummary[]>([]);
  const [selected, setSelected] = useState<BacktestDetail | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      setRuns(await apiGet<BacktestSummary[]>('/api/backtest?limit=20'));
    } catch {}
  };

  useEffect(() => {
    apiGet<string[]>('/api/backtest/strategies').then(setStrategies).catch(() => {});
    refresh();
    const i = setInterval(refresh, 3000);
    return () => clearInterval(i);
  }, []);

  const run = async () => {
    setBusy(true);
    try {
      const payload = {
        ...form,
        from_ts: new Date(form.from_ts).toISOString(),
        to_ts: new Date(form.to_ts).toISOString(),
      };
      const created = await apiPost<BacktestSummary>('/api/backtest/run', payload);
      await refresh();
      setSelected(await apiGet<BacktestDetail>(`/api/backtest/${created.id}`));
    } finally {
      setBusy(false);
    }
  };

  const loadDetail = async (id: number) => {
    setSelected(await apiGet<BacktestDetail>(`/api/backtest/${id}`));
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Backtest</h1>

      <div className="card grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
        <Field label="Strategy">
          <select
            className="bg-bg-accent rounded px-2 py-1 w-full"
            value={form.strategy}
            onChange={(e) => setForm({ ...form, strategy: e.target.value })}
          >
            {strategies.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Timeframe">
          <select
            className="bg-bg-accent rounded px-2 py-1 w-full"
            value={form.timeframe}
            onChange={(e) => setForm({ ...form, timeframe: e.target.value })}
          >
            {['1m', '5m', '15m'].map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </Field>
        <Field label="From (UTC)">
          <input
            type="datetime-local"
            className="bg-bg-accent rounded px-2 py-1 w-full"
            value={form.from_ts}
            onChange={(e) => setForm({ ...form, from_ts: e.target.value })}
          />
        </Field>
        <Field label="To (UTC)">
          <input
            type="datetime-local"
            className="bg-bg-accent rounded px-2 py-1 w-full"
            value={form.to_ts}
            onChange={(e) => setForm({ ...form, to_ts: e.target.value })}
          />
        </Field>
        <Field label="Initial $">
          <input
            type="number"
            className="bg-bg-accent rounded px-2 py-1 w-full font-mono"
            value={form.initial_capital}
            onChange={(e) =>
              setForm({ ...form, initial_capital: parseFloat(e.target.value) })
            }
          />
        </Field>
        <Field label="Leverage">
          <input
            type="number"
            className="bg-bg-accent rounded px-2 py-1 w-full font-mono"
            value={form.leverage}
            onChange={(e) => setForm({ ...form, leverage: parseInt(e.target.value) })}
          />
        </Field>
        <Field label="Risk per trade (%)">
          <input
            type="number"
            step="0.1"
            className="bg-bg-accent rounded px-2 py-1 w-full font-mono"
            value={form.risk_per_trade_pct}
            onChange={(e) =>
              setForm({ ...form, risk_per_trade_pct: parseFloat(e.target.value) })
            }
          />
        </Field>
        <button className="btn-primary disabled:opacity-50" disabled={busy} onClick={run}>
          {busy ? 'Running…' : 'Run backtest'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-1">
          <h2 className="text-sm uppercase tracking-wider text-gray-400 mb-3">Runs</h2>
          <ul className="divide-y divide-bg-accent/40 max-h-[400px] overflow-y-auto text-sm">
            {runs.map((r) => (
              <li
                key={r.id}
                onClick={() => loadDetail(r.id)}
                className={`py-2 cursor-pointer hover:bg-bg-accent/30 ${
                  selected?.id === r.id ? 'bg-bg-accent/40' : ''
                }`}
              >
                <div className="flex justify-between">
                  <span className="font-mono text-gray-400">#{r.id}</span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="text-xs text-gray-400">
                  {r.strategy} · {r.timeframe}
                </div>
                <div className="text-xs">
                  {r.total_return_pct != null ? (
                    <span
                      className={
                        r.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'
                      }
                    >
                      {r.total_return_pct >= 0 ? '+' : ''}
                      {r.total_return_pct.toFixed(2)}%
                    </span>
                  ) : (
                    '—'
                  )}{' '}
                  · {r.total_trades ?? 0} trades
                </div>
              </li>
            ))}
            {!runs.length && (
              <li className="py-6 text-center text-gray-500">No runs yet.</li>
            )}
          </ul>
        </div>

        <div className="lg:col-span-2 space-y-4">
          {selected ? (
            <DetailView run={selected} />
          ) : (
            <div className="card text-sm text-gray-500">
              Select a run on the left or launch a new backtest above.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs">
      <span className="text-gray-400 mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function StatusBadge({ status }: { status: BacktestStatus }) {
  const color =
    status === 'COMPLETED'
      ? 'bg-green-500/20 text-green-300'
      : status === 'RUNNING'
      ? 'bg-blue-500/20 text-blue-300 animate-pulse'
      : status === 'FAILED'
      ? 'bg-red-500/20 text-red-300'
      : 'bg-gray-500/20 text-gray-300';
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${color}`}>{status}</span>;
}

function DetailView({ run }: { run: BacktestDetail }) {
  return (
    <>
      <div className="card grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <Stat label="Strategy" value={run.strategy} />
        <Stat label="Status" value={run.status} />
        <Stat
          label="Return"
          value={
            run.total_return_pct != null
              ? `${run.total_return_pct >= 0 ? '+' : ''}${run.total_return_pct.toFixed(2)}%`
              : '—'
          }
          tone={(run.total_return_pct ?? 0) >= 0 ? 'pos' : 'neg'}
        />
        <Stat label="Final equity" value={`${run.final_equity?.toFixed(2) ?? '—'} $`} />
        <Stat label="Sharpe" value={run.sharpe?.toFixed(2) ?? '—'} />
        <Stat label="Profit factor" value={run.profit_factor?.toFixed(2) ?? '—'} />
        <Stat label="Max DD" value={`${run.max_drawdown_pct?.toFixed(2) ?? '—'}%`} tone="neg" />
        <Stat label="Winrate" value={`${run.winrate?.toFixed(1) ?? '—'}%`} />
        <Stat label="Trades" value={run.total_trades?.toString() ?? '0'} />
        <Stat label="Expectancy" value={run.expectancy?.toFixed(2) ?? '—'} />
        <Stat label="Leverage" value={`x${run.leverage}`} />
        <Stat label="Risk" value={`${run.risk_per_trade_pct}%`} />
      </div>

      {run.error && (
        <div className="card text-sm text-red-300 whitespace-pre-wrap">{run.error}</div>
      )}

      {run.equity_curve && run.equity_curve.length > 0 && (
        <EquityCurve points={run.equity_curve} />
      )}

      {run.trades && run.trades.length > 0 && (
        <div className="card">
          <h2 className="text-sm uppercase tracking-wider text-gray-400 mb-3">
            Simulated trades
          </h2>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 uppercase sticky top-0 bg-bg-card">
                <tr className="border-b border-bg-accent">
                  <th className="text-left py-1.5 px-2">Side</th>
                  <th className="text-right py-1.5 px-2">Entry</th>
                  <th className="text-right py-1.5 px-2">Exit</th>
                  <th className="text-right py-1.5 px-2">PnL</th>
                  <th className="text-right py-1.5 px-2">%</th>
                  <th className="text-left py-1.5 px-2">Reason</th>
                  <th className="text-left py-1.5 px-2">Opened</th>
                </tr>
              </thead>
              <tbody>
                {run.trades.map((t, i) => (
                  <tr key={i} className="border-b border-bg-accent/30">
                    <td className="py-1 px-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs ${
                          t.side === 'BUY'
                            ? 'bg-green-500/20 text-green-300'
                            : 'bg-red-500/20 text-red-300'
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="py-1 px-2 text-right font-mono">{t.entry.toFixed(2)}</td>
                    <td className="py-1 px-2 text-right font-mono">
                      {t.exit?.toFixed(2) ?? '—'}
                    </td>
                    <td
                      className={`py-1 px-2 text-right font-mono ${
                        (t.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {t.pnl != null
                        ? `${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}`
                        : '—'}
                    </td>
                    <td className="py-1 px-2 text-right font-mono">
                      {t.pnl_pct != null ? `${t.pnl_pct.toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-1 px-2 text-xs">{t.close_reason}</td>
                    <td className="py-1 px-2 text-xs text-gray-400">
                      {t.opened_at ? new Date(t.opened_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'pos' | 'neg';
}) {
  const color =
    tone === 'pos' ? 'text-green-400' : tone === 'neg' ? 'text-red-400' : 'text-gray-100';
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`font-mono ${color}`}>{value}</div>
    </div>
  );
}

function EquityCurve({ points }: { points: EquityPoint[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const data: LineData[] = useMemo(
    () =>
      points.map((p) => ({
        time: (new Date(p.ts).getTime() / 1000) as Time,
        value: p.equity,
      })),
    [points]
  );

  useEffect(() => {
    if (!containerRef.current) return;
    const chart: IChartApi = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#131826' },
        textColor: '#cbd5e1',
      },
      grid: {
        vertLines: { color: '#1B2235' },
        horzLines: { color: '#1B2235' },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const series: ISeriesApi<'Line'> = chart.addLineSeries({
      color: '#FFD700',
      lineWidth: 2,
    });
    series.setData(data);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data]);

  return (
    <div className="card h-[300px]">
      <h2 className="text-sm uppercase tracking-wider text-gray-400 mb-2">Equity curve</h2>
      <div ref={containerRef} className="w-full h-[240px]" />
    </div>
  );
}
