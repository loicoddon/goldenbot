# 🪙 GoldenBot — Virtual XAU/USD AI Trading Bot

> A **100% virtual** algorithmic trading laboratory for gold (XAU/USD).
> No real broker, no real money — pure simulation with AI-assisted analysis, news context, and a full web dashboard.

![status](https://img.shields.io/badge/status-experimental-orange)
![python](https://img.shields.io/badge/python-3.12-blue)
![next.js](https://img.shields.io/badge/next.js-14-black)
![docker](https://img.shields.io/badge/docker-compose-blue)

---

## ✨ What it does

- 📈 Streams real-time XAU/USD prices (TwelveData WS + OANDA failover, supervised auto-restart)
- 🧠 Multiple pluggable strategies: EMA crossover, SMC (order blocks + FVG), Wyckoff (spring/upthrust)
- 🤖 AI analysis before AND after each trade (Claude API or local Ollama, with auto-fallback)
- 📰 Economic calendar + news sentiment (Finnhub, with country whitelist for high-impact classification)
- ⚖️ Risk management: x500 leverage, confidence-mapped lot sizing, per-session confidence overrides, news blackout window
- 📊 Backtesting engine with full metrics (Sharpe, Profit Factor, Max DD, Winrate, Expectancy)
- 🌐 Mobile-first dashboard (Next.js + Tailwind) — live chart, trades table, settings, backtest UI, bottom-tab nav on phones
- 💬 Discord notifications on every trade open/close + portfolio snapshot
- 💾 PostgreSQL persistence — everything survives restarts

---

## 🏗️ Architecture

```
                    ┌──────────────────────┐
                    │   TwelveData / OANDA │  (XAU/USD live ticks)
                    │   Finnhub (news)     │
                    └──────────┬───────────┘
                               │ WS / REST
                ┌──────────────▼────────────────┐
                │     Backend  (FastAPI 0.115)  │
                │  ┌──────────┐ ┌─────────────┐ │
                │  │ Price /  │ │  Strategy   │ │
                │  │ News     │─│  Registry   │ │
                │  │ Feeds    │ │ (EMA/SMC/W) │ │
                │  └──────────┘ └──────┬──────┘ │
                │  ┌────────────────────▼────┐  │
                │  │ Risk · Trading · AI     │  │
                │  │ Optimizer · Backtest    │  │
                │  └────────┬─────────┬──────┘  │
                │           │         │         │
                │  ┌────────▼──┐  ┌───▼──────┐  │
                │  │ Postgres  │  │  Redis   │  │
                │  └────┬──────┘  └──┬───────┘  │
                └───────┼────────────┼──────────┘
                        │            │ pub/sub
              ┌─────────▼─┐    ┌─────▼────────┐
              │ Frontend  │    │ Discord Bot  │
              │ (Next.js) │    │ (discord.py) │
              └───────────┘    └──────────────┘
```

---

## 🚀 Installation

GoldenBot ships as a Docker Compose stack — same commands work on **macOS** and **Linux**. The only OS-specific bit is the Ollama setup if you want to run the AI locally.

### 1. Prerequisites

| Requirement | macOS | Linux |
|-------------|-------|-------|
| **Docker + Compose v2** | [Docker Desktop](https://docs.docker.com/desktop/install/mac-install/) | `docker` + `docker-compose-plugin` from your distro |
| **Git** | `brew install git` | `apt install git` / `dnf install git` |
| **(Optional) Ollama for local AI** | `brew install ollama` then `ollama serve` | [Linux installer](https://ollama.com/download/linux): `curl -fsSL https://ollama.com/install.sh \| sh` |

### 💻 Hardware requirements

GoldenBot itself is light — the AI stack is what dictates your RAM needs.

#### Without local AI (`AI_PROVIDER=stub` or `claude`)

The Docker stack (Postgres + Redis + backend + frontend + Discord bot) runs comfortably on:

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **RAM** | 4 GB | 8 GB |
| **CPU** | 2 cores (x86 / Apple Silicon) | 4+ cores |
| **Disk** | 5 GB (images + a few weeks of trading data) | 20 GB (long-term history + backtests) |
| **Network** | broadband | broadband |
| **OS** | macOS 12+ · Ubuntu 22.04+ · Debian 12+ · Fedora 38+ | same |

> 💡 Use `AI_PROVIDER=claude` if you want quality AI without buying hardware — Claude API runs in the cloud, your machine just needs the Docker stack.

#### With local AI (`AI_PROVIDER=ollama`)

Add the model's footprint to the Docker stack baseline. Pick based on what you have:

| Ollama model | Disk | RAM needed for inference | Total system RAM (with Docker) |
|--------------|------|--------------------------|-------------------------------|
| `qwen2.5:3b` | 2 GB | ~3 GB | **8 GB** min · 12 GB rec. |
| `llama3.1:8b` | 5 GB | ~5 GB | **12 GB** min · 16 GB rec. |
| `qwen2.5:14b` | 9 GB | ~9 GB | **20 GB** min · **24 GB+** rec. |
| `qwen2.5:32b` | 20 GB | ~20 GB | **32 GB+** rec. |

**Inference speed**:
- **Apple Silicon (M1/M2/M3/M4)** : unified memory + Neural Engine make even 14B run smoothly. Best price/perf for this project.
- **Linux + NVIDIA GPU** : `ollama` auto-uses CUDA. RTX 3060 12 GB handles 8-14B models well.
- **Linux CPU-only** : works but expect 5-15s per analysis on a 14B model. Consider `qwen2.5:3b` or `llama3.1:8b` instead.

> ⚠️ **Watch out for OOM**: even with 24 GB RAM, running `qwen2.5:14b` alongside Docker Desktop's allocation (typically 8 GB) can leave too little headroom. If you see `model requires more system memory` errors, either drop to a smaller model or raise Docker Desktop's memory limit in its Settings → Resources panel.

#### Network usage

Steady-state per day (1m trading on XAU/USD):
- **TwelveData WS** : ~5 MB inbound
- **Finnhub REST** : ~1 MB inbound (calendar + news polls)
- **Anthropic API** : ~50 KB / trade analysis (Claude only)
- **Discord** : negligible

Total < **20 MB/day** — runs fine on any home connection.

You'll also need free API keys (all take <2 min to obtain):

| Service | Required? | Where |
|---------|-----------|-------|
| **TwelveData** | yes (or mock mode) | https://twelvedata.com/account/api-keys — free tier 800 req/day |
| **Finnhub** | yes (for news) | https://finnhub.io/dashboard — free tier 60 req/min |
| **Discord Bot Token** | optional | https://discord.com/developers/applications → New App → Bot |
| **Anthropic API** | optional (for Claude AI) | https://console.anthropic.com/ |
| **OANDA v20 demo** | optional (failover feed) | https://www.oanda.com/demo-account/ (regional restrictions apply) |

### 2. Clone & configure

```bash
git clone https://github.com/<YOUR-USERNAME>/goldenbot.git
cd goldenbot
cp .env.example .env
$EDITOR .env   # fill in your API keys
```

Minimal `.env` to get started — TwelveData key + Finnhub key are enough:

```dotenv
TWELVEDATA_API_KEY=your_twelvedata_key
FINNHUB_API_KEY=your_finnhub_key
AI_PROVIDER=stub          # set to "claude" or "ollama" once you're ready
POSTGRES_PASSWORD=$(openssl rand -hex 16)   # generate a random one
```

> 💡 **No keys?** Leave `TWELVEDATA_API_KEY` empty — the price feed will run in **mock mode** (synthetic random walk around $2380). Lets you explore the UI offline.

### 3. Build & launch

```bash
docker compose up --build -d
```

First build pulls Python/Node images and installs deps — takes 3-5 min. Subsequent boots are <10s.

### 4. Open the dashboard

| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:3010 |
| API docs (Swagger) | http://localhost:8001/docs |
| API health | http://localhost:8001/health |

The bot starts **disabled** by default. Click **Start** in the StatusBar at the top of the dashboard.

### 5. Stop / restart

```bash
docker compose stop          # stop everything (state preserved)
docker compose start         # restart (resumes engine if enabled)
docker compose down          # stop + remove containers (volumes kept)
docker compose down -v       # NUCLEAR: also wipes DB and Redis
```

---

## 🧭 Quick tour of how it works

### A. The trading loop (per tick)

```
TwelveData WS ─▶ tick ($4480.17) ─▶ BarAggregator (60s buckets)
                                          │
                                          ├─ if bar closed ─▶ Strategy.evaluate()
                                          │                       │
                                          │                       ▼
                                          │              ┌──────────────────┐
                                          │              │ Signal generated │
                                          │              │ (BUY/SELL/HOLD)  │
                                          │              └────────┬─────────┘
                                          │                       │
                                          │              ┌────────▼─────────┐
                                          │              │ Risk Manager     │
                                          │              │ - news blackout? │
                                          │              │ - daily limits?  │
                                          │              │ - margin check?  │
                                          │              │ - position size  │
                                          │              └────────┬─────────┘
                                          │                       │
                                          │              ┌────────▼─────────┐
                                          │              │ AI pre-trade     │
                                          │              │ Claude / Ollama  │
                                          │              │ (REJECT/PROCEED/ │
                                          │              │  REDUCE_SIZE)    │
                                          │              └────────┬─────────┘
                                          │                       │
                                          ├─ open trade ◀─────────┘
                                          │
                                          └─ check SL/TP for open trades ─▶ close + PnL
                                                                              │
                                                                              ▼
                                                                       Post-trade AI analysis
                                                                              │
                                                                              ▼
                                                                       Discord notification
```

### B. Strategies

All strategies live in `backend/app/services/strategies/` and follow the same interface:

- **`ema_crossover`** (default) — fast EMA crosses slow EMA + RSI gate + ATR-based SL/TP. The confidence formula uses a piecewise mapping on `atr/price` calibrated for high-price assets like gold (typical XAU/USD scalping confidence range: 30-50).
- **`smc`** — Smart Money Concepts: detects Fair Value Gaps, liquidity sweeps, order blocks
- **`wyckoff`** — detects range-bound consolidation with spring (false break below) / upthrust (false break above)

Enable multiple in parallel via the **Settings** page or the API:
```bash
curl -X PATCH http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"strategies_enabled": ["ema_crossover", "smc"]}'
```

The engine picks the highest weighted-confidence signal per bar.

### C. AI providers

Choose with `AI_PROVIDER` in `.env`:

| Provider | Cost | Quality | Setup |
|----------|------|---------|-------|
| `stub` | free | none (passthrough) | no setup |
| `ollama` | free | good | run Ollama on host + `ollama pull qwen2.5:14b` |
| `claude` | ~$5-10/mo | best | set `ANTHROPIC_API_KEY` in `.env` |

**Smart fallback**: if Ollama fails 3 times in a row (OOM, timeout), the bot automatically falls back to Claude (if key configured).

**Multi-IA voting** (optional): 4 specialized agents (Technical, News/Sentiment, Risk, Decisional) that vote in parallel. Enable via `multi_ai_enabled: true` in settings.

### D. Risk management

| Setting | Default | Notes |
|---------|---------|-------|
| `leverage` | x500 | retail forex/CFD typical |
| `risk_per_trade_pct` | 1% | of equity (used when lot bounds are disabled) |
| `min_lot_size` / `max_lot_size` | 0 / 0 | when > 0, overrides risk % with confidence-mapped lot size |
| `confidence_for_max_lot` | 60 | confidence value at which size reaches `max_lot_size`. Lower = more aggressive ramp on modest setups (e.g. 50 makes a conf-40 signal use ~67% of the lot range) |
| `confidence_skip_low` / `confidence_skip_high` | 0 / 0 | when `skip_high > skip_low`, signals whose confidence falls in `[skip_low, skip_high]` are rejected. Use when an empirically toxic confidence band is identified (a real example: this account's `[35, 45]` bucket had 23% winrate vs 55% in `[25, 35]`, so skipping it surgically beats raising `min_confidence`) |
| `daily_loss_limit_pct` | 5% | engine auto-stops past this. Set very high (9999) to disable in lab mode |
| `max_trades_per_day` | 10 | anti-overtrading. Set very high to remove the cap |
| `news_filter_enabled` | true | block ±15min around high-impact events |
| `news_block_before_min` / `news_block_after_min` | 15 / 15 | minutes of blackout around each high-impact event |
| `session_min_confidence` | `{}` | per-session confidence override, e.g. `{"asia": 95, "london": 30, "ny": 30}` to choke off Asia thin liquidity |
| `max_open_positions` | 1 | multi-position cap |

Sizing curve (with `min_confidence=20`, `confidence_for_max_lot=60`, `min/max_lot=0.1/0.3`):

| Confidence | Lots |
|------------|------|
| 20 | 0.10 |
| 30 | 0.15 |
| 40 | 0.20 |
| 50 | 0.25 |
| ≥ 60 | 0.30 |

Trades store `notional`, `margin_used`, `leverage`, and the lot quantity (`size / 100`) so you can audit exposure exactly.

### E. Backtest

Hit the `/backtest` page in the dashboard:
1. Pick a strategy, timeframe, date range
2. Set initial capital, leverage, risk %
3. Click **Run backtest**
4. View equity curve + all simulated trades + Sharpe / Profit Factor / Max DD

Or via API:
```bash
curl -X POST http://localhost:8001/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "smc",
    "timeframe": "1m",
    "from_ts": "2026-05-19T00:00:00Z",
    "to_ts": "2026-05-20T00:00:00Z",
    "initial_capital": 1000,
    "leverage": 500,
    "risk_per_trade_pct": 1.0
  }'
```

The engine reads historical `price_ticks` from your DB — the more your bot has been running, the more history available to backtest.

### F. News + economic calendar

- **Finnhub economic calendar** polled every 5 min — CPI, NFP, FOMC, GDP auto-classified as `high` impact
- **Country whitelist for high-impact**: events are only tagged `high` when they come from a country that actually moves XAU/USD (US, EU/EUR, DE, FR, GB, JP, CN, CH). A "Retail Sales" print from Macau or a Rwanda rate decision is downgraded to `medium`, so the bot doesn't get blocked by irrelevant macro events
- **Finnhub general news** polled every 2 min, filtered for gold/USD/macro relevance (keyword matching)
- Live in the dashboard's **News panel** (calendar + headlines, color-coded by impact)
- High-impact events trigger the **news blackout window**: trades blocked ±15min (configurable)

### G. Discord notifications

If `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID` are set, you'll get rich embeds for:
- 🟢 **Trade OPEN**: side, entry, SL, TP, size, confidence, reason, current portfolio snapshot
- ✅/❌ **Trade CLOSED**: entry, exit, PnL ($ and % of risk), duration, close reason, updated portfolio
- 🚨 **Alerts**: drawdown breaches, optimizer adjustments, manual closes

---

## 🛠️ Common ops

```bash
# Tail backend logs
docker compose logs -f backend

# Query DB directly
docker compose exec db psql -U goldenbot -d goldenbot -c "SELECT * FROM trades ORDER BY id DESC LIMIT 10;"

# Toggle the engine without UI
curl -X POST http://localhost:8001/api/bot/start
curl -X POST http://localhost:8001/api/bot/stop

# Patch a setting on-the-fly (no restart)
curl -X PATCH http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"min_confidence": 35, "ai_pretrade_enabled": false}'

# Per-session confidence override (block Asia thin-liquidity carnage)
curl -X PATCH http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"session_min_confidence": {"asia": 95, "london": 30, "ny": 30}}'

# Tune the lot sizing curve aggressiveness
curl -X PATCH http://localhost:8001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"confidence_for_max_lot": 50}'   # lower = more aggressive ramp

# Check the active price feed
curl http://localhost:8001/api/feed/status

# Force-restart the feed (e.g. after manual quota recovery)
curl -X POST http://localhost:8001/api/feed/restart
```

### Dev mode

The backend runs without `uvicorn --reload` by default — `--reload` was found
to leave zombie asyncio tasks polling external APIs after each code change.
To iterate quickly on backend code, set `UVICORN_RELOAD=1` in `.env` and
`docker compose up -d --force-recreate backend`.

---

## 📁 Project layout

```
goldenbot/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers (trades, portfolio, news, backtest, settings, ws, bot, feed)
│   │   ├── core/          # logger, redis bus
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic
│   │   ├── services/
│   │   │   ├── ai/        # analyzer + multi-agent voting + prompts
│   │   │   ├── feeds/     # price feed backends (TwelveData, OANDA, failover)
│   │   │   ├── strategies/ # ema_crossover, smc, wyckoff (pluggable registry)
│   │   │   ├── trading_engine.py
│   │   │   ├── risk.py
│   │   │   ├── portfolio_service.py
│   │   │   ├── news_feed.py
│   │   │   ├── optimizer.py
│   │   │   ├── backtest.py
│   │   │   └── engine_runner.py    # ties it all together
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js 14 app router (dashboard, trades, backtest, settings)
│   │   ├── components/    # PriceChart, PortfolioCard, TradesTable, NewsPanel, ...
│   │   └── lib/           # API client + WebSocket hook
│   └── Dockerfile
├── discord_bot/
│   ├── bot.py
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🗺️ Roadmap

- [x] **Phase 1** — virtual trading, price feed, dashboard, Discord, DB persistence, AI interface
- [x] **Phase 2** — news (Finnhub), real pre/post-trade AI, news filter, auto-optimizer
- [x] **Phase 3** — backtest, SMC + Wyckoff, multi-IA voting, OANDA failover, multi-position, sessions
- [ ] **Phase 4** — Reinforcement learning, chart screenshot capture (Playwright), bar-by-bar replay UI, Alembic migrations

---

## ⚠️ Disclaimer

This is a **laboratory project** for studying algorithmic trading and AI decision-making. It does **not** place real orders, does **not** connect to a live broker, and has **no** capacity to lose real money — by design.

The strategies, risk parameters, and AI prompts are research-grade — they are not investment advice and should never be used as such. Past simulated performance does not imply future results.

API keys committed in `.env` stay strictly local thanks to `.gitignore`. Never push your `.env` file. Use `.env.example` to share required variables.

---

## 📜 License

MIT — see `LICENSE`.

## 🤝 Contributions

Issues and PRs welcome. Particularly interested in:
- Additional strategies (volume profile, harmonic patterns)
- Alternative AI providers (local Llama variants, Mistral)
- Alembic migration setup
- Web-based replay engine
