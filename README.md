# 🪙 GoldenBot — Virtual XAU/USD AI Trading Bot

> A **100% virtual** algorithmic trading laboratory for gold (XAU/USD).
> No real broker, no real money — pure simulation with AI-assisted analysis, news context, and a full web dashboard.

![status](https://img.shields.io/badge/status-experimental-orange)
![python](https://img.shields.io/badge/python-3.12-blue)
![next.js](https://img.shields.io/badge/next.js-14-black)
![docker](https://img.shields.io/badge/docker-compose-blue)

---

## ✨ What it does

- 📈 Streams real-time XAU/USD prices (TwelveData WS + OANDA failover)
- 🧠 Multiple pluggable strategies: EMA crossover, SMC (order blocks + FVG), Wyckoff (spring/upthrust)
- 🤖 AI analysis before AND after each trade (Claude API or local Ollama)
- 📰 Economic calendar + news sentiment (Finnhub)
- ⚖️ Risk management: leverage (x500 by default), position sizing by lot bounds or risk %, news blackout window, daily loss limit
- 📊 Backtesting engine with full metrics (Sharpe, Profit Factor, Max DD, Winrate, Expectancy)
- 🌐 Web dashboard (Next.js) with live chart, trades table, settings, backtest UI
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

- **`ema_crossover`** (default) — fast EMA crosses slow EMA + RSI gate + ATR-based SL/TP
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
| `risk_per_trade_pct` | 1% | of equity |
| `min_lot_size` / `max_lot_size` | 0 / 0 | when > 0, overrides risk % with confidence-mapped lot size |
| `daily_loss_limit_pct` | 5% | engine auto-stops past this |
| `max_trades_per_day` | 10 | anti-overtrading |
| `news_filter_enabled` | true | block ±15min around high-impact events |
| `max_open_positions` | 1 | multi-position cap |

Trades store `notional`, `margin_used`, and `leverage` per row so you can audit exposure.

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

# Check the active price feed
curl http://localhost:8001/api/feed/status
```

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
