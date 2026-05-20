from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EconomicEvent(Base):
    """Calendar event (CPI, NFP, FOMC, etc.) from Finnhub economic calendar."""

    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(128), index=True)  # dedup key
    country: Mapped[str] = mapped_column(String(8), default="US")
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    impact: Mapped[str] = mapped_column(String(16), default="low")  # low|medium|high
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_economic_events_key"),
        Index("ix_eco_events_impact_time", "impact", "event_time"),
    )


class NewsItem(Base):
    """Headline relevant to XAU/USD (gold, USD, geopolitics, FED)."""

    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="finnhub")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    headline: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1..1
    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
