from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.news import EconomicEvent, NewsItem
from app.schemas.news import EconomicEventOut, NewsItemOut

router = APIRouter()


@router.get("/events", response_model=list[EconomicEventOut])
async def list_events(
    hours: int = Query(48, ge=1, le=720),
    impact: str | None = Query(None, description="low|medium|high"),
    db: AsyncSession = Depends(get_db),
):
    horizon = datetime.now(timezone.utc) + timedelta(hours=hours)
    stmt = (
        select(EconomicEvent)
        .where(EconomicEvent.event_time >= datetime.now(timezone.utc) - timedelta(hours=2))
        .where(EconomicEvent.event_time <= horizon)
        .order_by(EconomicEvent.event_time)
        .limit(200)
    )
    if impact:
        stmt = stmt.where(EconomicEvent.impact == impact.lower())
    rows = (await db.scalars(stmt)).all()
    return list(rows)


@router.get("/headlines", response_model=list[NewsItemOut])
async def list_headlines(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        await db.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= since)
            .order_by(desc(NewsItem.published_at))
            .limit(limit)
        )
    ).all()
    return list(rows)
