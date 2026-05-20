"""Portfolio bookkeeping: initialization, equity tracking, statistics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.bot_settings import BotSettings
from app.models.portfolio import EquitySnapshot, Portfolio
from app.models.trade import Trade, TradeSide, TradeStatus


class PortfolioService:
    @staticmethod
    async def ensure_singletons(session: AsyncSession) -> tuple[Portfolio, BotSettings]:
        portfolio = await session.scalar(select(Portfolio).where(Portfolio.id == 1))
        if portfolio is None:
            portfolio = Portfolio(
                id=1,
                initial_capital=settings.initial_capital,
                balance=settings.initial_capital,
                equity=settings.initial_capital,
                peak_equity=settings.initial_capital,
            )
            session.add(portfolio)

        bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
        if bot is None:
            bot = BotSettings(
                id=1,
                enabled=False,
                timeframe=settings.default_timeframe,
                risk_per_trade_pct=settings.risk_per_trade_pct,
                daily_loss_limit_pct=settings.daily_loss_limit_pct,
                max_trades_per_day=settings.max_trades_per_day,
                leverage=settings.leverage,
                ai_provider=settings.ai_provider,
            )
            session.add(bot)

        await session.commit()
        await session.refresh(portfolio)
        await session.refresh(bot)
        return portfolio, bot

    @staticmethod
    def _unrealized_pnl(trade: Trade, current_price: float) -> float:
        if trade.side == TradeSide.BUY:
            return (current_price - trade.entry_price) * trade.size
        return (trade.entry_price - current_price) * trade.size

    @staticmethod
    async def recalculate(
        session: AsyncSession, current_price: float | None
    ) -> Portfolio:
        portfolio = await session.scalar(select(Portfolio).where(Portfolio.id == 1))
        assert portfolio is not None

        realized = await session.scalar(
            select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                Trade.status == TradeStatus.CLOSED
            )
        ) or 0.0

        unrealized = 0.0
        if current_price is not None:
            open_trades = (
                await session.scalars(
                    select(Trade).where(Trade.status == TradeStatus.OPEN)
                )
            ).all()
            for t in open_trades:
                unrealized += PortfolioService._unrealized_pnl(t, current_price)

        portfolio.realized_pnl = float(realized)
        portfolio.unrealized_pnl = float(unrealized)
        portfolio.balance = portfolio.initial_capital + portfolio.realized_pnl
        portfolio.equity = portfolio.balance + portfolio.unrealized_pnl
        if portfolio.equity > portfolio.peak_equity:
            portfolio.peak_equity = portfolio.equity
        if portfolio.peak_equity > 0:
            dd = (portfolio.peak_equity - portfolio.equity) / portfolio.peak_equity * 100
            portfolio.max_drawdown_pct = max(portfolio.max_drawdown_pct, dd)

        won = await session.scalar(
            select(func.count(Trade.id)).where(
                Trade.status == TradeStatus.CLOSED, Trade.pnl > 0
            )
        ) or 0
        lost = await session.scalar(
            select(func.count(Trade.id)).where(
                Trade.status == TradeStatus.CLOSED, Trade.pnl <= 0
            )
        ) or 0
        portfolio.winning_trades = int(won)
        portfolio.losing_trades = int(lost)
        portfolio.total_trades = int(won + lost)
        portfolio.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(portfolio)
        return portfolio

    @staticmethod
    async def snapshot(session: AsyncSession) -> EquitySnapshot:
        portfolio = await session.scalar(select(Portfolio).where(Portfolio.id == 1))
        assert portfolio is not None
        snap = EquitySnapshot(
            balance=portfolio.balance,
            equity=portfolio.equity,
            drawdown_pct=portfolio.max_drawdown_pct,
        )
        session.add(snap)
        await session.commit()
        await session.refresh(snap)
        return snap

    @staticmethod
    async def stats(session: AsyncSession) -> dict:
        rows = (
            await session.scalars(
                select(Trade).where(Trade.status == TradeStatus.CLOSED)
            )
        ).all()
        if not rows:
            return {
                "winrate": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }
        wins = [t.pnl for t in rows if t.pnl and t.pnl > 0]
        losses = [t.pnl for t in rows if t.pnl and t.pnl <= 0]
        n = len(rows)
        winrate = (len(wins) / n) * 100 if n else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        expectancy = (winrate / 100) * avg_win + (1 - winrate / 100) * avg_loss
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss else float("inf")

        pnls = [t.pnl for t in rows if t.pnl is not None]
        if len(pnls) > 1:
            import statistics

            mu = statistics.mean(pnls)
            sigma = statistics.stdev(pnls) or 1e-9
            sharpe = mu / sigma
        else:
            sharpe = 0.0

        return {
            "winrate": winrate,
            "expectancy": expectancy,
            "profit_factor": profit_factor if profit_factor != float("inf") else 999.0,
            "sharpe_ratio": sharpe,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }
