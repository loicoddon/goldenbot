from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis_bus import CHANNEL_ALERT, bus
from app.database import get_db
from app.models.trade import CloseReason, Trade, TradeStatus
from app.schemas.trade import TradeAnalysisOut, TradeOut
from app.services.price_feed import price_feed
from app.services.trading_engine import TradingEngine

router = APIRouter()


@router.get("", response_model=list[TradeOut])
async def list_trades(
    status: str | None = Query(None, description="OPEN | CLOSED | CANCELLED"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Trade).order_by(desc(Trade.opened_at)).limit(limit)
    if status:
        try:
            stmt = stmt.where(Trade.status == TradeStatus(status.upper()))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid status") from e
    rows = (await db.scalars(stmt)).all()
    return list(rows)


@router.get("/open", response_model=list[TradeOut])
async def list_open_trades(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(select(Trade).where(Trade.status == TradeStatus.OPEN))
    ).all()
    return list(rows)


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    trade = await db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.get("/{trade_id}/analysis", response_model=TradeAnalysisOut | None)
async def get_trade_analysis(trade_id: int, db: AsyncSession = Depends(get_db)):
    trade = await db.get(Trade, trade_id, options=[selectinload(Trade.analysis)])
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade.analysis


@router.post("/{trade_id}/close")
async def close_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    trade = await db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status != TradeStatus.OPEN:
        raise HTTPException(status_code=400, detail="Trade is not open")
    price = price_feed.last_price
    if price is None:
        raise HTTPException(status_code=503, detail="No live price available")
    closed = await TradingEngine.close_trade(db, trade, price, CloseReason.MANUAL)
    await bus.publish(
        CHANNEL_ALERT,
        {"level": "info", "message": f"Trade #{closed.id} manually closed at {price}"},
    )
    return {"id": closed.id, "exit_price": closed.exit_price, "pnl": closed.pnl}
