from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.price import PriceTick
from app.services.price_feed import price_feed

router = APIRouter()


@router.get("/latest")
async def latest_price():
    return {
        "price": price_feed.last_price,
        "timestamp": (
            price_feed.last_timestamp.isoformat() if price_feed.last_timestamp else None
        ),
    }


@router.get("/history")
async def price_history(
    minutes: int = Query(60, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(minutes=minutes)
    rows = (
        await db.scalars(
            select(PriceTick)
            .where(PriceTick.timestamp >= since)
            .order_by(PriceTick.timestamp)
        )
    ).all()
    return [
        {"timestamp": r.timestamp.isoformat(), "price": r.price}
        for r in rows
    ]
