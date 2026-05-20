'use client';

import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { fetcher } from '@/lib/api';

type Trade = {
  id: number;
  side: string;
  status: string;
  entry_price: number;
  exit_price: number | null;
  stop_loss: number;
  take_profit: number;
  size: number;
  pnl: number | null;
  pnl_pct: number | null;
  confidence_score: number | null;
  reason: string | null;
  close_reason: string | null;
  opened_at: string;
  closed_at: string | null;
};

export function TradesTable({ limit = 20 }: { limit?: number }) {
  const router = useRouter();
  const { data } = useSWR<Trade[]>(`/api/trades?limit=${limit}`, fetcher, {
    refreshInterval: 4000,
  });

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm uppercase tracking-wider text-gray-400">Recent trades</h2>
        <span className="text-xs text-gray-500">{data?.length ?? 0} shown</span>
      </div>

      {/* Mobile: card list */}
      <ul className="md:hidden divide-y divide-bg-accent/40">
        {data?.map((t) => {
          const pnlClass =
            t.pnl == null
              ? 'text-gray-300'
              : t.pnl >= 0
              ? 'text-green-400'
              : 'text-red-400';
          return (
            <li
              key={t.id}
              onClick={() => router.push(`/trades/${t.id}`)}
              className="py-2.5 cursor-pointer active:bg-bg-accent/40"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-gray-500">#{t.id}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      t.side === 'BUY'
                        ? 'bg-green-500/20 text-green-300'
                        : 'bg-red-500/20 text-red-300'
                    }`}
                  >
                    {t.side}
                  </span>
                  <span className="text-[10px] text-gray-500">{t.status}</span>
                </div>
                <span className={`font-mono text-sm font-semibold ${pnlClass}`}>
                  {t.pnl != null
                    ? `${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)} $`
                    : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-gray-400 font-mono">
                <span>
                  {t.entry_price.toFixed(2)} → {t.exit_price?.toFixed(2) ?? '—'}
                </span>
                <span className="text-[10px]">
                  conf {t.confidence_score?.toFixed(0) ?? '—'} ·{' '}
                  {new Date(t.opened_at).toLocaleString([], {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            </li>
          );
        })}
        {!data?.length && (
          <li className="py-6 text-center text-gray-500 text-sm">No trades yet.</li>
        )}
      </ul>

      {/* Desktop: full table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-gray-500 uppercase">
            <tr className="border-b border-bg-accent">
              <th className="text-left py-2 px-2">#</th>
              <th className="text-left py-2 px-2">Side</th>
              <th className="text-right py-2 px-2">Entry</th>
              <th className="text-right py-2 px-2">Exit</th>
              <th className="text-right py-2 px-2">SL</th>
              <th className="text-right py-2 px-2">TP</th>
              <th className="text-right py-2 px-2">Size</th>
              <th className="text-right py-2 px-2">Conf.</th>
              <th className="text-right py-2 px-2">PnL</th>
              <th className="text-left py-2 px-2">Status</th>
              <th className="text-left py-2 px-2">Opened</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((t) => {
              const pnlClass =
                t.pnl == null
                  ? 'text-gray-300'
                  : t.pnl >= 0
                  ? 'text-green-400'
                  : 'text-red-400';
              return (
                <tr
                  key={t.id}
                  onClick={() => router.push(`/trades/${t.id}`)}
                  className="border-b border-bg-accent/40 hover:bg-bg-accent/40 cursor-pointer"
                >
                  <td className="py-1.5 px-2 font-mono text-gray-400">{t.id}</td>
                  <td className="py-1.5 px-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                        t.side === 'BUY'
                          ? 'bg-green-500/20 text-green-300'
                          : 'bg-red-500/20 text-red-300'
                      }`}
                    >
                      {t.side}
                    </span>
                  </td>
                  <td className="py-1.5 px-2 text-right font-mono">{t.entry_price.toFixed(2)}</td>
                  <td className="py-1.5 px-2 text-right font-mono">
                    {t.exit_price?.toFixed(2) ?? '—'}
                  </td>
                  <td className="py-1.5 px-2 text-right font-mono text-red-300/80">
                    {t.stop_loss.toFixed(2)}
                  </td>
                  <td className="py-1.5 px-2 text-right font-mono text-green-300/80">
                    {t.take_profit.toFixed(2)}
                  </td>
                  <td className="py-1.5 px-2 text-right font-mono">{t.size.toFixed(4)}</td>
                  <td className="py-1.5 px-2 text-right font-mono">
                    {t.confidence_score?.toFixed(0) ?? '—'}
                  </td>
                  <td className={`py-1.5 px-2 text-right font-mono ${pnlClass}`}>
                    {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-1.5 px-2 text-xs">{t.status}</td>
                  <td className="py-1.5 px-2 text-xs text-gray-400">
                    {new Date(t.opened_at).toLocaleString()}
                  </td>
                </tr>
              );
            })}
            {!data?.length && (
              <tr>
                <td colSpan={11} className="text-center text-gray-500 py-6 text-sm">
                  No trades yet — start the engine when settings allow.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
