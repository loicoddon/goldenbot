'use client';

import useSWR from 'swr';
import { fetcher } from '@/lib/api';

type Event = {
  id: number;
  country: string;
  title: string;
  impact: string;
  actual: number | null;
  estimate: number | null;
  previous: number | null;
  unit: string | null;
  event_time: string;
};

type Headline = {
  id: number;
  source: string;
  headline: string;
  summary: string | null;
  url: string | null;
  published_at: string;
  relevance: number | null;
};

const impactStyle: Record<string, string> = {
  high: 'bg-red-500/20 text-red-300 border-red-500/40',
  medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  low: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
};

export function NewsPanel() {
  const { data: events } = useSWR<Event[]>('/api/news/events?hours=48', fetcher, {
    refreshInterval: 60_000,
  });
  const { data: headlines } = useSWR<Headline[]>(
    '/api/news/headlines?hours=24&limit=20',
    fetcher,
    { refreshInterval: 60_000 }
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm uppercase tracking-wider text-gray-400">
            Economic calendar
          </h2>
          <span className="text-xs text-gray-500">{events?.length ?? 0} events · next 48h</span>
        </div>
        <ul className="divide-y divide-bg-accent/40 max-h-[360px] overflow-y-auto">
          {events?.map((ev) => {
            const t = new Date(ev.event_time);
            const past = t.getTime() < Date.now();
            return (
              <li key={ev.id} className="py-2 flex items-center gap-3 text-sm">
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                    impactStyle[ev.impact] ?? impactStyle.low
                  }`}
                >
                  {ev.impact.toUpperCase()}
                </span>
                <span className="text-xs text-gray-400 font-mono w-24 shrink-0">
                  {t.toLocaleString([], {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
                <span className="text-xs text-gray-500 font-mono w-8 shrink-0">
                  {ev.country}
                </span>
                <span className={`flex-1 ${past ? 'text-gray-500' : 'text-gray-100'}`}>
                  {ev.title}
                </span>
                <span className="text-xs font-mono text-gray-400 hidden md:inline">
                  {ev.actual != null
                    ? `A:${ev.actual}`
                    : ev.estimate != null
                    ? `E:${ev.estimate}`
                    : ''}
                </span>
              </li>
            );
          })}
          {!events?.length && (
            <li className="py-6 text-center text-gray-500 text-sm">
              No upcoming events (check Finnhub API key).
            </li>
          )}
        </ul>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm uppercase tracking-wider text-gray-400">Gold-relevant headlines</h2>
          <span className="text-xs text-gray-500">{headlines?.length ?? 0} · last 24h</span>
        </div>
        <ul className="divide-y divide-bg-accent/40 max-h-[360px] overflow-y-auto">
          {headlines?.map((n) => (
            <li key={n.id} className="py-2 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-xs text-gray-500 font-mono shrink-0">
                  {new Date(n.published_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
                <div className="flex-1">
                  {n.url ? (
                    <a
                      href={n.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-gold transition-colors"
                    >
                      {n.headline}
                    </a>
                  ) : (
                    <span>{n.headline}</span>
                  )}
                  <div className="text-xs text-gray-500 mt-0.5">
                    {n.source}
                    {n.relevance != null && (
                      <span className="ml-2">rel: {(n.relevance * 100).toFixed(0)}%</span>
                    )}
                  </div>
                </div>
              </div>
            </li>
          ))}
          {!headlines?.length && (
            <li className="py-6 text-center text-gray-500 text-sm">
              No headlines yet. Polling Finnhub every 2 min.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
