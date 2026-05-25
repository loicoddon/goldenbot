"""Risk management: position sizing, daily limits, anti-overtrading, news filter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_settings import BotSettings
from app.models.news import EconomicEvent
from app.models.portfolio import Portfolio
from app.models.trade import Trade, TradeStatus


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""
    size: float = 0.0
    risk_amount: float = 0.0
    leverage: int = 500
    notional: float = 0.0
    margin_used: float = 0.0


class RiskManager:
    @staticmethod
    async def evaluate(
        session: AsyncSession,
        entry_price: float,
        stop_loss: float,
        confidence: float = 50.0,
    ) -> RiskDecision:
        portfolio = await session.scalar(select(Portfolio).where(Portfolio.id == 1))
        bot_settings = await session.scalar(select(BotSettings).where(BotSettings.id == 1))

        if portfolio is None or bot_settings is None:
            return RiskDecision(False, "Portfolio or settings not initialized.")

        if not bot_settings.enabled:
            return RiskDecision(False, "Bot is disabled.")

        # Confidence skip range — reject signals in an empirically toxic band.
        skip_lo = float(bot_settings.confidence_skip_low or 0)
        skip_hi = float(bot_settings.confidence_skip_high or 0)
        if skip_hi > skip_lo and skip_lo <= confidence <= skip_hi:
            return RiskDecision(
                False,
                f"Confidence {confidence:.1f} in skip range [{skip_lo:.0f}, {skip_hi:.0f}].",
            )

        # Multi-position cap: respect per-strategy/per-bot limit.
        max_open = max(1, bot_settings.max_open_positions)
        open_count = await session.scalar(
            select(func.count(Trade.id)).where(Trade.status == TradeStatus.OPEN)
        ) or 0
        if open_count >= max_open:
            return RiskDecision(
                False,
                f"Max open positions reached ({open_count}/{max_open}).",
            )

        # News blackout window — block trade opens around high-impact events
        if bot_settings.news_filter_enabled:
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(minutes=bot_settings.news_block_after_min)
            window_end = now + timedelta(minutes=bot_settings.news_block_before_min)
            ev = await session.scalar(
                select(EconomicEvent)
                .where(EconomicEvent.impact == "high")
                .where(EconomicEvent.event_time >= window_start)
                .where(EconomicEvent.event_time <= window_end)
                .order_by(EconomicEvent.event_time)
                .limit(1)
            )
            if ev is not None:
                return RiskDecision(
                    False,
                    f"News blackout: '{ev.title}' ({ev.country}) at "
                    f"{ev.event_time.isoformat()} is within block window.",
                )

        # Daily loss limit
        today_start = datetime.combine(datetime.utcnow().date(), time.min, tzinfo=timezone.utc)
        today_realized = await session.scalar(
            select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                Trade.status == TradeStatus.CLOSED,
                Trade.closed_at >= today_start,
            )
        ) or 0.0
        daily_loss_pct = (today_realized / portfolio.initial_capital) * 100
        if daily_loss_pct <= -bot_settings.daily_loss_limit_pct:
            return RiskDecision(
                False,
                f"Daily loss limit reached ({daily_loss_pct:.2f}% / "
                f"-{bot_settings.daily_loss_limit_pct:.2f}%).",
            )

        # Daily trade count limit
        today_count = await session.scalar(
            select(func.count(Trade.id)).where(Trade.opened_at >= today_start)
        ) or 0
        if today_count >= bot_settings.max_trades_per_day:
            return RiskDecision(
                False,
                f"Max trades/day reached ({today_count}/{bot_settings.max_trades_per_day}).",
            )

        # Position size
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return RiskDecision(False, "Invalid stop-loss distance.")

        # Lot-bounded sizing takes precedence over risk-based when configured.
        # Mapping: confidence [min_confidence, confidence_for_max_lot] -> lots [min, max] (linear).
        # confidence_for_max_lot tuning lets us reach max_lot at a realistic
        # ceiling (e.g. 50-60) instead of an unreachable 100 — effectively an
        # "exponential" feel on the practical confidence range.
        if (bot_settings.max_lot_size or 0) > 0:
            min_oz = max(0.0, (bot_settings.min_lot_size or 0.0) * 100)
            max_oz = bot_settings.max_lot_size * 100
            if min_oz > max_oz:
                min_oz, max_oz = max_oz, min_oz
            min_c = float(bot_settings.min_confidence or 0)
            max_c = float(bot_settings.confidence_for_max_lot or 100)
            if max_c <= min_c:
                max_c = min_c + 1.0
            span = max_c - min_c
            norm = max(0.0, min(1.0, (confidence - min_c) / span))
            size = min_oz + norm * (max_oz - min_oz)
            risk_amount = size * sl_distance
        else:
            risk_amount = portfolio.equity * (bot_settings.risk_per_trade_pct / 100)
            size = risk_amount / sl_distance

        if size <= 0:
            return RiskDecision(False, "Computed position size is zero.")

        # Leverage cap — cap size so notional <= equity * leverage
        leverage = max(1, bot_settings.leverage)
        max_notional = portfolio.equity * leverage
        notional = entry_price * size
        if notional > max_notional:
            size = max_notional / entry_price
            notional = entry_price * size
            risk_amount = size * sl_distance
        margin_used = notional / leverage

        # Check free margin (sum of margins on existing open trades)
        open_trades = (
            await session.scalars(select(Trade).where(Trade.status == TradeStatus.OPEN))
        ).all()
        used_margin = sum((t.margin_used or 0.0) for t in open_trades)
        free_margin = portfolio.equity - used_margin
        if margin_used > free_margin:
            return RiskDecision(
                False,
                f"Insufficient free margin: need {margin_used:.2f}$ "
                f"(notional {notional:.2f}$ @ x{leverage}), free {free_margin:.2f}$.",
            )

        return RiskDecision(
            allowed=True,
            size=size,
            risk_amount=risk_amount,
            leverage=leverage,
            notional=notional,
            margin_used=margin_used,
        )
