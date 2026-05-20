'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiGet } from '@/lib/api';

type Trade = {
  id: number;
  side: string;
  status: string;
  symbol: string;
  entry_price: number;
  exit_price: number | null;
  stop_loss: number;
  take_profit: number;
  size: number;
  risk_amount: number;
  leverage: number;
  notional: number;
  margin_used: number;
  pnl: number | null;
  pnl_pct: number | null;
  confidence_score: number | null;
  strategy: string;
  timeframe: string;
  reason: string | null;
  close_reason: string | null;
  opened_at: string;
  closed_at: string | null;
};

type Analysis = {
  id: number;
  phase: string;
  provider: string;
  quality_score: number | null;
  confidence_score: number | null;
  summary: string | null;
  improvements: string | null;
  created_at: string;
};

export default function TradeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [trade, setTrade] = useState<Trade | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    apiGet<Trade>(`/api/trades/${id}`).then(setTrade).catch((e) => setError(String(e)));
    apiGet<Analysis | null>(`/api/trades/${id}/analysis`)
      .then((a) => setAnalysis(a))
      .catch(() => setAnalysis(null));
  }, [id]);

  if (error) {
    return (
      <div className="space-y-4">
        <Link href="/trades" className="text-sm text-gold hover:underline">
          ← Back to trades
        </Link>
        <div className="card text-red-300">{error}</div>
      </div>
    );
  }
  if (!trade) return <div className="card animate-pulse">Loading…</div>;

  const pnlClass =
    trade.pnl == null ? '' : trade.pnl >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="space-y-4">
      <Link href="/trades" className="text-sm text-gold hover:underline">
        ← Back to trades
      </Link>
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold">
            Trade #{trade.id} —{' '}
            <span className={trade.side === 'BUY' ? 'text-green-400' : 'text-red-400'}>
              {trade.side}
            </span>{' '}
            {trade.symbol}
          </h1>
          <span className="text-sm text-gray-400">{trade.status}</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <Cell label="Entry" value={trade.entry_price.toFixed(2)} />
          <Cell label="Exit" value={trade.exit_price?.toFixed(2) ?? '—'} />
          <Cell label="SL" value={trade.stop_loss.toFixed(2)} />
          <Cell label="TP" value={trade.take_profit.toFixed(2)} />
          <Cell label="Size (oz)" value={trade.size.toFixed(4)} />
          <Cell label="Risk" value={`${trade.risk_amount.toFixed(2)} $`} />
          <Cell label="Leverage" value={`x${trade.leverage}`} />
          <Cell label="Notional" value={`${trade.notional.toFixed(2)} $`} />
          <Cell label="Margin used" value={`${trade.margin_used.toFixed(2)} $`} />
          <Cell
            label="PnL"
            value={
              trade.pnl != null
                ? `${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)} $ (${trade.pnl_pct?.toFixed(2)}%)`
                : '—'
            }
            valueClass={pnlClass}
          />
          <Cell label="Confidence" value={trade.confidence_score?.toFixed(1) ?? '—'} />
          <Cell label="Strategy" value={trade.strategy} />
          <Cell label="Timeframe" value={trade.timeframe} />
          <Cell label="Opened" value={new Date(trade.opened_at).toLocaleString()} />
          <Cell
            label="Closed"
            value={trade.closed_at ? new Date(trade.closed_at).toLocaleString() : '—'}
          />
        </div>
        {trade.reason && (
          <div className="mt-4 text-sm">
            <div className="text-xs text-gray-500">Initial reason</div>
            <div className="text-gray-200">{trade.reason}</div>
          </div>
        )}
        {trade.close_reason && (
          <div className="mt-2 text-sm">
            <div className="text-xs text-gray-500">Close reason</div>
            <div className="text-gray-200">{trade.close_reason}</div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm uppercase tracking-wider text-gray-400">AI analysis</h2>
          {analysis && (
            <span className="text-xs text-gray-500">
              {analysis.provider} · {analysis.phase} · quality {analysis.quality_score?.toFixed(0) ?? '—'}/100
            </span>
          )}
        </div>
        {analysis ? (
          <div className="space-y-3 text-sm">
            <div>
              <div className="text-xs text-gray-500 mb-1">Summary</div>
              <div className="text-gray-100 whitespace-pre-wrap">{analysis.summary || '—'}</div>
            </div>
            {analysis.improvements && (
              <div>
                <div className="text-xs text-gray-500 mb-1">Improvements</div>
                <div className="text-gray-100 whitespace-pre-wrap">{analysis.improvements}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-gray-500">
            No AI analysis yet (either still pending, or `ai_analysis_every` frequency hasn't matched).
          </div>
        )}
      </div>
    </div>
  );
}

function Cell({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`font-mono ${valueClass || 'text-gray-100'}`}>{value}</div>
    </div>
  );
}
