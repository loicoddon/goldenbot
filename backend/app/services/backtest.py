"""Backtesting engine.

Replays historical PriceTick rows for a symbol/timeframe, aggregates them into
bars, feeds them to a strategy, and simulates trade execution with the same
SL/TP rules as the live engine. Outputs equity curve + metrics.

Uses leverage/risk_per_trade_pct from the backtest run config (not live settings).
"""

from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models.backtest import BacktestRun, BacktestStatus
from app.models.price import PriceTick
from app.services.strategies import BarAggregator, get_strategy


@dataclass
class SimTrade:
    side: str  # BUY | SELL
    entry: float
    sl: float
    tp: float
    size: float
    risk: float
    leverage: int
    notional: float
    opened_at: datetime
    closed_at: datetime | None = None
    exit: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    close_reason: str | None = None
    confidence: float | None = None
    reason: str | None = None


def _tf_to_seconds(tf: str) -> int:
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    if tf.endswith("h"):
        return int(tf[:-1]) * 3600
    return 60


async def run_backtest(run_id: int) -> None:
    """Top-level entrypoint — run a queued BacktestRun by id."""
    async with SessionLocal() as session:
        run = await session.get(BacktestRun, run_id)
        if run is None:
            logger.error("Backtest {} not found", run_id)
            return
        if run.status != BacktestStatus.PENDING:
            logger.info("Backtest {} status={}, skipping", run_id, run.status)
            return
        run.status = BacktestStatus.RUNNING
        await session.commit()

    try:
        await _execute(run_id)
    except Exception as e:
        logger.exception("Backtest {} failed: {}", run_id, e)
        async with SessionLocal() as session:
            run = await session.get(BacktestRun, run_id)
            if run:
                run.status = BacktestStatus.FAILED
                run.error = str(e)[:2000]
                run.finished_at = datetime.utcnow()
                await session.commit()


async def _execute(run_id: int) -> None:
    async with SessionLocal() as session:
        run = await session.get(BacktestRun, run_id)
        assert run is not None
        params = run.params or {}
        strategy = get_strategy(run.strategy, **params)
        agg = BarAggregator(timeframe_seconds=_tf_to_seconds(run.timeframe))

        # Stream ticks in batches
        from_ts = run.from_ts
        to_ts = run.to_ts
        symbol = run.symbol
        leverage = run.leverage
        risk_pct = run.risk_per_trade_pct
        equity = run.initial_capital
        peak_equity = equity
        max_dd = 0.0

        open_trades: list[SimTrade] = []
        closed_trades: list[SimTrade] = []
        equity_curve: list[dict[str, Any]] = []
        bar_count = 0

        stmt = (
            select(PriceTick)
            .where(PriceTick.symbol == symbol)
            .where(PriceTick.timestamp >= from_ts)
            .where(PriceTick.timestamp <= to_ts)
            .order_by(PriceTick.timestamp)
        )
        result = await session.stream_scalars(stmt)
        async for tick in result:
            ts_epoch = int(tick.timestamp.timestamp())
            bar = agg.add_tick(tick.price, ts_epoch)

            # Check SL/TP on every tick
            still_open: list[SimTrade] = []
            for t in open_trades:
                exit_price, reason = _check_exit(t, tick.price)
                if reason is not None:
                    _close_trade(t, exit_price, reason, tick.timestamp)
                    equity += t.pnl or 0.0
                    closed_trades.append(t)
                else:
                    still_open.append(t)
            open_trades = still_open

            if bar is not None:
                bar_count += 1
                strategy.add_bar(bar)
                signal = strategy.evaluate()
                if signal and not open_trades:
                    sl_dist = abs(signal.price - signal.stop_loss)
                    if sl_dist > 0:
                        risk_amount = equity * risk_pct / 100
                        size = risk_amount / sl_dist
                        notional = signal.price * size
                        max_notional = equity * leverage
                        if notional > max_notional:
                            size = max_notional / signal.price
                            notional = signal.price * size
                            risk_amount = size * sl_dist
                        t = SimTrade(
                            side=signal.direction,
                            entry=signal.price,
                            sl=signal.stop_loss,
                            tp=signal.take_profit,
                            size=size,
                            risk=risk_amount,
                            leverage=leverage,
                            notional=notional,
                            opened_at=tick.timestamp,
                            confidence=signal.confidence,
                            reason=signal.reason,
                        )
                        open_trades.append(t)

                # Update equity curve at bar close
                unrealized = sum(_unrealized(t, tick.price) for t in open_trades)
                current_equity = equity + unrealized
                if current_equity > peak_equity:
                    peak_equity = current_equity
                if peak_equity > 0:
                    dd = (peak_equity - current_equity) / peak_equity * 100
                    max_dd = max(max_dd, dd)
                if bar_count % 10 == 0:
                    equity_curve.append(
                        {
                            "ts": tick.timestamp.isoformat(),
                            "equity": current_equity,
                            "balance": equity,
                        }
                    )

        # Force-close any remaining trades at last price
        last_price = (
            await session.scalar(
                select(PriceTick.price)
                .where(PriceTick.symbol == symbol)
                .where(PriceTick.timestamp <= to_ts)
                .order_by(PriceTick.timestamp.desc())
                .limit(1)
            )
        )
        if last_price is not None:
            for t in open_trades:
                _close_trade(t, last_price, "END_OF_BACKTEST", to_ts)
                equity += t.pnl or 0.0
                closed_trades.append(t)
        open_trades.clear()

        metrics = _compute_metrics(closed_trades, run.initial_capital, equity, max_dd)
        run.status = BacktestStatus.COMPLETED
        run.final_equity = equity
        run.total_return_pct = (equity - run.initial_capital) / run.initial_capital * 100
        run.sharpe = metrics["sharpe"]
        run.profit_factor = metrics["profit_factor"]
        run.max_drawdown_pct = max_dd
        run.winrate = metrics["winrate"]
        run.expectancy = metrics["expectancy"]
        run.total_trades = len(closed_trades)
        run.trades = [_trade_to_dict(t) for t in closed_trades]
        run.equity_curve = equity_curve
        run.finished_at = datetime.utcnow()
        await session.commit()
        logger.info(
            "Backtest {} done: trades={} return={:+.2f}% sharpe={:.2f} dd={:.2f}%",
            run.id,
            len(closed_trades),
            run.total_return_pct,
            run.sharpe,
            max_dd,
        )


def _check_exit(t: SimTrade, price: float) -> tuple[float, str | None]:
    if t.side == "BUY":
        if price <= t.sl:
            return t.sl, "STOP_LOSS"
        if price >= t.tp:
            return t.tp, "TAKE_PROFIT"
    else:
        if price >= t.sl:
            return t.sl, "STOP_LOSS"
        if price <= t.tp:
            return t.tp, "TAKE_PROFIT"
    return price, None


def _unrealized(t: SimTrade, price: float) -> float:
    if t.side == "BUY":
        return (price - t.entry) * t.size
    return (t.entry - price) * t.size


def _close_trade(t: SimTrade, exit_price: float, reason: str, closed_at: datetime) -> None:
    if t.side == "BUY":
        pnl = (exit_price - t.entry) * t.size
    else:
        pnl = (t.entry - exit_price) * t.size
    t.exit = exit_price
    t.pnl = pnl
    t.pnl_pct = (pnl / t.risk) * 100 if t.risk else 0.0
    t.closed_at = closed_at
    t.close_reason = reason


def _trade_to_dict(t: SimTrade) -> dict:
    return {
        "side": t.side,
        "entry": t.entry,
        "exit": t.exit,
        "sl": t.sl,
        "tp": t.tp,
        "size": t.size,
        "risk": t.risk,
        "notional": t.notional,
        "leverage": t.leverage,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "close_reason": t.close_reason,
        "confidence": t.confidence,
        "reason": t.reason,
    }


def _compute_metrics(
    trades: list[SimTrade], initial: float, final: float, max_dd_pct: float
) -> dict:
    if not trades:
        return {
            "winrate": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "sharpe": 0.0,
        }
    pnls = [t.pnl or 0.0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    winrate = len(wins) / len(pnls) * 100
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = (winrate / 100) * avg_win + (1 - winrate / 100) * avg_loss
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss else (999.0 if wins else 0.0)
    if len(pnls) > 1:
        mu = statistics.mean(pnls)
        sigma = statistics.stdev(pnls) or 1e-9
        sharpe = mu / sigma
    else:
        sharpe = 0.0
    return {
        "winrate": winrate,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "sharpe": sharpe,
    }
