from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.portfolio import EquitySnapshot
from app.schemas.portfolio import EquityPoint, PortfolioOut, PortfolioStats
from app.services.portfolio_service import PortfolioService
from app.services.price_feed import price_feed

router = APIRouter()


@router.get("", response_model=PortfolioOut)
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    portfolio = await PortfolioService.recalculate(db, price_feed.last_price)
    return portfolio


@router.get("/stats", response_model=PortfolioStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await PortfolioService.stats(db)


@router.get("/equity", response_model=list[EquityPoint])
async def get_equity(
    limit: int = Query(500, ge=10, le=5000),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.scalars(
            select(EquitySnapshot).order_by(desc(EquitySnapshot.timestamp)).limit(limit)
        )
    ).all()
    return list(reversed(rows))
