"""Virtual trading engine: opens, monitors, closes trades against live ticks."""

from __future__ import annotations

from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_bus import CHANNEL_TRADE, bus
from app.models.signal import Signal as SignalRow
from app.models.trade import CloseReason, Trade, TradeSide, TradeStatus
from app.services.ai.analyzer import PreTradeResult
from app.services.portfolio_service import PortfolioService
from app.services.risk import RiskManager
from app.services.strategies import StrategySignal


class TradingEngine:
    @staticmethod
    async def open_trade(
        session: AsyncSession,
        signal: StrategySignal,
        timeframe: str,
        strategy_name: str,
        pretrade: PreTradeResult | None = None,
        size_multiplier: float = 1.0,
    ) -> Trade | None:
        risk = await RiskManager.evaluate(
            session,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            confidence=signal.confidence,
        )

        indicators = dict(signal.indicators or {})
        if pretrade is not None:
            indicators["ai_pretrade"] = {
                "score": pretrade.score,
                "recommendation": pretrade.recommendation,
                "factors": pretrade.factors,
                "warnings": pretrade.warnings,
                "summary": pretrade.summary,
            }

        signal_row = SignalRow(
            timeframe=timeframe,
            strategy=strategy_name,
            direction=signal.direction,
            price=signal.price,
            confidence=signal.confidence,
            reason=signal.reason,
            accepted=risk.allowed,
            rejection_reason=None if risk.allowed else risk.reason,
            indicators=indicators,
        )
        session.add(signal_row)

        if not risk.allowed:
            await session.commit()
            logger.info("Signal {} rejected: {}", signal.direction, risk.reason)
            return None

        side = TradeSide.BUY if signal.direction == "BUY" else TradeSide.SELL
        mult = max(0.1, min(1.0, size_multiplier))
        sized = risk.size * mult
        risked = risk.risk_amount * mult
        notional = signal.price * sized
        margin = notional / max(1, risk.leverage)
        combined_conf = signal.confidence
        if pretrade is not None:
            combined_conf = (signal.confidence + pretrade.score) / 2

        meta = {"pretrade": indicators.get("ai_pretrade")} if pretrade else None
        trade = Trade(
            side=side,
            status=TradeStatus.OPEN,
            entry_price=signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            size=sized,
            risk_amount=risked,
            leverage=risk.leverage,
            notional=notional,
            margin_used=margin,
            confidence_score=combined_conf,
            strategy=strategy_name,
            timeframe=timeframe,
            reason=signal.reason,
            opened_at=datetime.utcnow(),
            meta=meta,
        )
        session.add(trade)
        await session.commit()
        await session.refresh(trade)

        logger.info(
            "OPEN {} {} @ {:.2f} SL={:.2f} TP={:.2f} size={:.4f} conf={:.1f}",
            side.value,
            trade.symbol,
            trade.entry_price,
            trade.stop_loss,
            trade.take_profit,
            trade.size,
            signal.confidence,
        )
        await bus.publish(
            CHANNEL_TRADE,
            {
                "event": "open",
                "trade": {
                    "id": trade.id,
                    "side": side.value,
                    "entry_price": trade.entry_price,
                    "stop_loss": trade.stop_loss,
                    "take_profit": trade.take_profit,
                    "size": trade.size,
                    "confidence": signal.confidence,
                    "reason": trade.reason,
                    "opened_at": trade.opened_at.isoformat(),
                },
            },
        )
        return trade

    @staticmethod
    async def check_exits(session: AsyncSession, current_price: float) -> list[Trade]:
        """Close any trades whose SL/TP is hit by current_price."""
        open_trades = (
            await session.scalars(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
        ).all()
        closed: list[Trade] = []
        for t in open_trades:
            close_reason: CloseReason | None = None
            if t.side == TradeSide.BUY:
                if current_price <= t.stop_loss:
                    close_reason = CloseReason.SL
                elif current_price >= t.take_profit:
                    close_reason = CloseReason.TP
            else:
                if current_price >= t.stop_loss:
                    close_reason = CloseReason.SL
                elif current_price <= t.take_profit:
                    close_reason = CloseReason.TP
            if close_reason:
                await TradingEngine.close_trade(session, t, current_price, close_reason)
                closed.append(t)
        return closed

    @staticmethod
    async def close_trade(
        session: AsyncSession,
        trade: Trade,
        exit_price: float,
        reason: CloseReason,
    ) -> Trade:
        if trade.side == TradeSide.BUY:
            pnl = (exit_price - trade.entry_price) * trade.size
        else:
            pnl = (trade.entry_price - exit_price) * trade.size
        pnl_pct = (pnl / trade.risk_amount) * 100 if trade.risk_amount else 0.0
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.status = TradeStatus.CLOSED
        trade.close_reason = reason
        trade.closed_at = datetime.utcnow()
        await session.commit()
        await session.refresh(trade)

        logger.info(
            "CLOSE #{} {} @ {:.2f} PnL={:+.2f}$ ({:+.2f}%) reason={}",
            trade.id,
            trade.side.value,
            exit_price,
            pnl,
            pnl_pct,
            reason.value,
        )
        await bus.publish(
            CHANNEL_TRADE,
            {
                "event": "close",
                "trade": {
                    "id": trade.id,
                    "side": trade.side.value,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "close_reason": reason.value,
                    "duration_s": (trade.closed_at - trade.opened_at).total_seconds(),
                },
            },
        )

        # Refresh portfolio
        await PortfolioService.recalculate(session, exit_price)
        return trade
