"""Engine runner: ties price feed, news feed, strategies, IA, trading engine together.

Phase 3: multi-strategy registry, multi-position support, session-adaptive
confidence thresholds, multi-IA voting committee, correlated-market context.
"""

from __future__ import annotations

import asyncio
import time as time_module
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.core.redis_bus import CHANNEL_PORTFOLIO, bus
from app.database import SessionLocal
from app.models.bot_settings import BotSettings
from app.services.ai.agents import vote as ai_vote
from app.services.ai.analyzer import PreTradeResult, get_analyzer
from app.services.correlated_feed import correlated_feed
from app.services.news_feed import news_feed
from app.services.optimizer import optimizer
from app.services.portfolio_service import PortfolioService
from app.services.price_feed import price_feed
from app.services.session import current_session, session_min_confidence
from app.services.strategies import BarAggregator, BaseStrategy, get_strategy
from app.services.trading_engine import TradingEngine

DEFAULT_STRATEGIES = ["ema_crossover"]


class EngineRunner:
    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        self._aggregator = BarAggregator(timeframe_seconds=60)
        self._lock = asyncio.Lock()
        self._started_at: datetime | None = None
        self._closed_since_analysis = 0
        self._closed_since_optimizer = 0

    def status(self) -> dict:
        return {
            "running": self._started_at is not None,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_price": price_feed.last_price,
            "last_tick_ts": (
                price_feed.last_timestamp.isoformat() if price_feed.last_timestamp else None
            ),
            "strategies": list(self._strategies.keys()),
            "session": current_session(),
        }

    async def bootstrap(self) -> None:
        async with SessionLocal() as session:
            _, bot = await PortfolioService.ensure_singletons(session)
        self._rebuild_strategies(bot)
        price_feed.subscribe(self._on_tick)
        await price_feed.start()
        await news_feed.start()
        await correlated_feed.start()
        if bot.enabled:
            await self.start()

    def _rebuild_strategies(self, bot: BotSettings) -> None:
        enabled = bot.strategies_enabled or DEFAULT_STRATEGIES
        self._strategies = {name: get_strategy(name) for name in enabled}

    async def start(self) -> None:
        async with self._lock:
            if self._started_at is None:
                self._started_at = datetime.utcnow()
                async with SessionLocal() as session:
                    bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
                    if bot:
                        bot.enabled = True
                        await session.commit()
                        self._rebuild_strategies(bot)
                logger.info("Engine started: strategies={}", list(self._strategies))

    async def stop(self) -> None:
        async with self._lock:
            if self._started_at is not None:
                self._started_at = None
                async with SessionLocal() as session:
                    bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
                    if bot:
                        bot.enabled = False
                        await session.commit()
                logger.info("Engine stopped")

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def _on_tick(self, payload: dict[str, Any]) -> None:
        price = float(payload["price"])
        ts_iso = payload["timestamp"]
        try:
            ts_epoch = int(datetime.fromisoformat(ts_iso).timestamp())
        except Exception:
            ts_epoch = int(time_module.time())

        bar = self._aggregator.add_tick(price, ts_epoch)
        if bar is not None:
            for s in self._strategies.values():
                s.add_bar(bar)

        async with SessionLocal() as session:
            closed = await TradingEngine.check_exits(session, price)
            for t in closed:
                self._closed_since_analysis += 1
                self._closed_since_optimizer += 1
                await self._maybe_run_post_analysis(session, t)
                await self._maybe_run_optimizer(session)

            if bar is not None:
                portfolio = await PortfolioService.recalculate(session, price)
                await bus.publish(
                    CHANNEL_PORTFOLIO,
                    {
                        "equity": portfolio.equity,
                        "balance": portfolio.balance,
                        "unrealized_pnl": portfolio.unrealized_pnl,
                        "realized_pnl": portfolio.realized_pnl,
                        "max_drawdown_pct": portfolio.max_drawdown_pct,
                    },
                )
                await PortfolioService.snapshot(session)

            if bar is not None and self._started_at is not None:
                await self._evaluate_strategies(session)

    async def _evaluate_strategies(self, session) -> None:
        bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
        if not bot:
            return

        # Apply per-session min_confidence override
        sess = current_session()
        min_conf = session_min_confidence(
            bot.min_confidence, bot.session_min_confidence, sess
        )

        # Collect signals from all enabled strategies, pick the highest confidence one
        weights = bot.strategy_weights or {}
        candidates = []
        for name, s in self._strategies.items():
            sig = s.evaluate()
            if sig is None:
                continue
            w = float(weights.get(name, 1.0))
            candidates.append((sig.confidence * w, sig, name))

        if not candidates:
            return
        candidates.sort(reverse=True, key=lambda x: x[0])
        weighted_conf, signal, strategy_name = candidates[0]
        if signal.confidence < min_conf:
            return

        pretrade: PreTradeResult | None = None
        size_mult = 1.0
        if bot.ai_pretrade_enabled:
            correlated = correlated_feed.snapshot
            try:
                if bot.multi_ai_enabled:
                    pretrade, _votes = await ai_vote(
                        session,
                        symbol=bot.symbol,
                        timeframe=bot.timeframe,
                        direction=signal.direction,
                        price=signal.price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        strategy_confidence=signal.confidence,
                        indicators=signal.indicators,
                        correlated=correlated,
                        weights=bot.ai_agent_weights,
                        provider=bot.ai_provider,
                    )
                else:
                    analyzer = get_analyzer(bot.ai_provider)
                    pretrade = await analyzer.analyze_pre_trade(
                        session,
                        symbol=bot.symbol,
                        timeframe=bot.timeframe,
                        direction=signal.direction,
                        price=signal.price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        strategy_confidence=signal.confidence,
                        indicators=signal.indicators,
                    )
            except Exception as e:
                logger.warning("Pre-trade IA crashed: {}", e)
                pretrade = None

            if pretrade is not None:
                if pretrade.recommendation == "REJECT":
                    logger.info("AI vetoed {} on {}: {}",
                                signal.direction, strategy_name, pretrade.summary)
                    return
                if pretrade.score < bot.ai_min_pretrade_score:
                    logger.info(
                        "AI score {:.1f} < min {:.1f} for {} — skipping",
                        pretrade.score, bot.ai_min_pretrade_score, strategy_name,
                    )
                    return
                if pretrade.recommendation == "REDUCE_SIZE":
                    size_mult = 0.5

        await TradingEngine.open_trade(
            session,
            signal,
            timeframe=bot.timeframe,
            strategy_name=strategy_name,
            pretrade=pretrade,
            size_multiplier=size_mult,
        )

    async def _maybe_run_post_analysis(self, session, trade) -> None:
        bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
        if not bot:
            return
        if self._closed_since_analysis < bot.ai_analysis_every:
            return
        self._closed_since_analysis = 0
        analyzer = get_analyzer(bot.ai_provider)
        try:
            await analyzer.analyze_post_trade(session, trade)
        except Exception as e:
            logger.warning("Post-trade analysis failed: {}", e)

    async def _maybe_run_optimizer(self, session) -> None:
        bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
        if not bot or not bot.optimizer_enabled:
            return
        if self._closed_since_optimizer < bot.optimizer_run_every_trades:
            return
        self._closed_since_optimizer = 0
        try:
            await optimizer.run(session)
        except Exception as e:
            logger.warning("Optimizer crashed: {}", e)


engine_runner = EngineRunner()
