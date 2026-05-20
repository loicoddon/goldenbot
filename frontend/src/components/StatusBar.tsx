'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/lib/api';

type BotStatus = {
  running: boolean;
  started_at: string | null;
  last_price: number | null;
  last_tick_ts: string | null;
};

export function StatusBar() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      setStatus(await apiGet<BotStatus>('/api/bot/status'));
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refresh();
    const i = setInterval(refresh, 3000);
    return () => clearInterval(i);
  }, []);

  const act = async (action: 'start' | 'stop' | 'restart') => {
    setBusy(true);
    try {
      await apiPost(`/api/bot/${action}`);
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card flex flex-wrap items-center gap-4 justify-between">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span
            className={`w-3 h-3 rounded-full ${
              status?.running ? 'bg-green-400 animate-pulse' : 'bg-gray-500'
            }`}
          />
          <span className="text-sm">
            {status?.running ? 'Engine running' : 'Engine stopped'}
          </span>
        </div>
        <div className="text-xs text-gray-400">
          Last price:{' '}
          <span className="text-gold font-mono">
            {status?.last_price ? status.last_price.toFixed(2) : '—'}
          </span>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          disabled={busy || status?.running}
          className="btn-primary disabled:opacity-40"
          onClick={() => act('start')}
        >
          Start
        </button>
        <button
          disabled={busy || !status?.running}
          className="btn-danger disabled:opacity-40"
          onClick={() => act('stop')}
        >
          Stop
        </button>
        <button
          disabled={busy}
          className="btn-ghost disabled:opacity-40"
          onClick={() => act('restart')}
        >
          Restart
        </button>
      </div>
    </div>
  );
}
