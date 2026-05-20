'use client';

import useSWR from 'swr';
import { fetcher } from '@/lib/api';

type Portfolio = {
  initial_capital: number;
  balance: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  max_drawdown_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
};

export function PortfolioCard() {
  const { data } = useSWR<Portfolio>('/api/portfolio', fetcher, {
    refreshInterval: 5000,
  });
  if (!data) return <div className="card animate-pulse">Loading portfolio…</div>;

  const pnl = data.equity - data.initial_capital;
  const pnlPct = (pnl / data.initial_capital) * 100;
  const won = pnl >= 0;

  return (
    <div className="card">
      <h2 className="text-sm uppercase tracking-wider text-gray-400 mb-3">Portfolio</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Equity" value={`$${data.equity.toFixed(2)}`} highlight />
        <Stat label="Balance" value={`$${data.balance.toFixed(2)}`} />
        <Stat
          label="Total PnL"
          value={`${won ? '+' : ''}${pnl.toFixed(2)} $ (${pnlPct.toFixed(2)}%)`}
          tone={won ? 'pos' : 'neg'}
        />
        <Stat
          label="Unrealized"
          value={`${data.unrealized_pnl >= 0 ? '+' : ''}${data.unrealized_pnl.toFixed(2)} $`}
          tone={data.unrealized_pnl >= 0 ? 'pos' : 'neg'}
        />
        <Stat label="Max DD" value={`${data.max_drawdown_pct.toFixed(2)}%`} tone="neg" />
        <Stat label="Trades" value={data.total_trades.toString()} />
        <Stat label="Wins" value={data.winning_trades.toString()} tone="pos" />
        <Stat label="Losses" value={data.losing_trades.toString()} tone="neg" />
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  highlight,
}: {
  label: string;
  value: string;
  tone?: 'pos' | 'neg';
  highlight?: boolean;
}) {
  const color =
    tone === 'pos'
      ? 'text-green-400'
      : tone === 'neg'
      ? 'text-red-400'
      : highlight
      ? 'text-gold'
      : 'text-gray-100';
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-mono ${color}`}>{value}</div>
    </div>
  );
}
