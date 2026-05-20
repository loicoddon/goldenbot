'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPatch } from '@/lib/api';

type BotSettings = {
  enabled: boolean;
  symbol: string;
  timeframe: string;
  strategy: string;
  risk_per_trade_pct: number;
  daily_loss_limit_pct: number;
  max_trades_per_day: number;
  min_confidence: number;
  leverage: number;
  min_lot_size: number;
  max_lot_size: number;
  ai_analysis_every: number;
  ai_provider: string;
  ai_pretrade_enabled: boolean;
  ai_min_pretrade_score: number;
  news_filter_enabled: boolean;
  news_block_before_min: number;
  news_block_after_min: number;
  optimizer_enabled: boolean;
  optimizer_window_trades: number;
  optimizer_run_every_trades: number;
  max_open_positions: number;
  session_min_confidence: Record<string, number> | null;
  strategies_enabled: string[] | null;
  strategy_weights: Record<string, number> | null;
  multi_ai_enabled: boolean;
  ai_agent_weights: Record<string, number> | null;
};

const AVAILABLE_STRATEGIES = ['ema_crossover', 'smc', 'wyckoff'];

export default function SettingsPage() {
  const [settings, setSettings] = useState<BotSettings | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    apiGet<BotSettings>('/api/settings').then(setSettings).catch(() => {});
  }, []);

  if (!settings) return <div className="card animate-pulse">Loading settings…</div>;

  const update = <K extends keyof BotSettings>(k: K, v: BotSettings[K]) =>
    setSettings({ ...settings, [k]: v });

  const save = async () => {
    const updated = await apiPatch<BotSettings>('/api/settings', settings);
    setSettings(updated);
    setSavedAt(new Date().toLocaleTimeString());
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Bot settings</h1>

      <Section title="Trading">
        <Row label="Timeframe">
          <select
            className="bg-bg-accent rounded px-2 py-1"
            value={settings.timeframe}
            onChange={(e) => update('timeframe', e.target.value)}
          >
            {['1m', '5m', '15m'].map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </Row>
        <Row label="Risk per trade (%)">
          <NumberInput
            value={settings.risk_per_trade_pct}
            min={0.1}
            max={10}
            step={0.1}
            onChange={(v) => update('risk_per_trade_pct', v)}
          />
        </Row>
        <Row label="Daily loss limit (%)">
          <NumberInput
            value={settings.daily_loss_limit_pct}
            min={0.5}
            max={50}
            step={0.5}
            onChange={(v) => update('daily_loss_limit_pct', v)}
          />
        </Row>
        <Row label="Max trades / day">
          <NumberInput
            value={settings.max_trades_per_day}
            min={1}
            max={200}
            step={1}
            onChange={(v) => update('max_trades_per_day', v)}
          />
        </Row>
        <Row label="Min strategy confidence (0-100)">
          <NumberInput
            value={settings.min_confidence}
            min={0}
            max={100}
            step={1}
            onChange={(v) => update('min_confidence', v)}
          />
        </Row>
        <Row label="Leverage (x)">
          <NumberInput
            value={settings.leverage}
            min={1}
            max={2000}
            step={1}
            onChange={(v) => update('leverage', v)}
          />
        </Row>
        <Row label="Min lot size (0 = disabled)">
          <NumberInput
            value={settings.min_lot_size}
            min={0}
            max={10}
            step={0.01}
            onChange={(v) => update('min_lot_size', v)}
          />
        </Row>
        <Row label="Max lot size (0 = disabled, overrides risk%)">
          <NumberInput
            value={settings.max_lot_size}
            min={0}
            max={10}
            step={0.01}
            onChange={(v) => update('max_lot_size', v)}
          />
        </Row>
      </Section>

      <Section title="AI">
        <Row label="Provider">
          <select
            className="bg-bg-accent rounded px-2 py-1"
            value={settings.ai_provider}
            onChange={(e) => update('ai_provider', e.target.value)}
          >
            {['stub', 'claude', 'ollama'].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </Row>
        <Row label="Pre-trade AI">
          <Toggle
            checked={settings.ai_pretrade_enabled}
            onChange={(v) => update('ai_pretrade_enabled', v)}
          />
        </Row>
        <Row label="Min AI pre-trade score (0-100)">
          <NumberInput
            value={settings.ai_min_pretrade_score}
            min={0}
            max={100}
            step={1}
            onChange={(v) => update('ai_min_pretrade_score', v)}
          />
        </Row>
        <Row label="Post-trade analysis every N trades">
          <select
            className="bg-bg-accent rounded px-2 py-1"
            value={settings.ai_analysis_every}
            onChange={(e) => update('ai_analysis_every', parseInt(e.target.value))}
          >
            {[1, 3, 5, 10, 20].map((n) => (
              <option key={n} value={n}>
                Every {n} trade{n > 1 ? 's' : ''}
              </option>
            ))}
          </select>
        </Row>
      </Section>

      <Section title="News filter">
        <Row label="Enabled">
          <Toggle
            checked={settings.news_filter_enabled}
            onChange={(v) => update('news_filter_enabled', v)}
          />
        </Row>
        <Row label="Block minutes BEFORE high-impact event">
          <NumberInput
            value={settings.news_block_before_min}
            min={0}
            max={120}
            step={1}
            onChange={(v) => update('news_block_before_min', v)}
          />
        </Row>
        <Row label="Block minutes AFTER high-impact event">
          <NumberInput
            value={settings.news_block_after_min}
            min={0}
            max={120}
            step={1}
            onChange={(v) => update('news_block_after_min', v)}
          />
        </Row>
      </Section>

      <Section title="Strategies (Phase 3)">
        <Row label="Enabled strategies">
          <div className="flex gap-2 flex-wrap">
            {AVAILABLE_STRATEGIES.map((s) => {
              const list = settings.strategies_enabled || ['ema_crossover'];
              const on = list.includes(s);
              return (
                <button
                  key={s}
                  onClick={() => {
                    const next = on ? list.filter((x) => x !== s) : [...list, s];
                    update('strategies_enabled', next.length ? next : ['ema_crossover']);
                  }}
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    on ? 'bg-gold text-black' : 'bg-bg-accent text-gray-300'
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </Row>
        <Row label="Max open positions">
          <NumberInput
            value={settings.max_open_positions}
            min={1}
            max={20}
            step={1}
            onChange={(v) => update('max_open_positions', v)}
          />
        </Row>
        <Row label="Multi-AI voting (4 agents)">
          <Toggle
            checked={settings.multi_ai_enabled}
            onChange={(v) => update('multi_ai_enabled', v)}
          />
        </Row>
      </Section>

      <Section title="Optimizer">
        <Row label="Enabled">
          <Toggle
            checked={settings.optimizer_enabled}
            onChange={(v) => update('optimizer_enabled', v)}
          />
        </Row>
        <Row label="Window trades">
          <NumberInput
            value={settings.optimizer_window_trades}
            min={5}
            max={200}
            step={1}
            onChange={(v) => update('optimizer_window_trades', v)}
          />
        </Row>
        <Row label="Run every N closed trades">
          <NumberInput
            value={settings.optimizer_run_every_trades}
            min={1}
            max={100}
            step={1}
            onChange={(v) => update('optimizer_run_every_trades', v)}
          />
        </Row>
      </Section>

      <div className="flex items-center justify-between">
        {savedAt && <span className="text-xs text-green-400">Saved at {savedAt}</span>}
        <button className="btn-primary ml-auto" onClick={save}>
          Save
        </button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card space-y-3">
      <h2 className="text-sm uppercase tracking-wider text-gray-400 border-b border-bg-accent pb-2">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-300">{label}</span>
      {children}
    </div>
  );
}

function NumberInput({
  value,
  min,
  max,
  step,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <input
      type="number"
      className="bg-bg-accent rounded px-2 py-1 w-28 font-mono text-right"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
    />
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
        checked ? 'bg-gold text-black' : 'bg-bg-accent text-gray-300'
      }`}
    >
      {checked ? 'ON' : 'OFF'}
    </button>
  );
}
