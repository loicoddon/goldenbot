from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class CloseReason(str, Enum):
    TP = "TAKE_PROFIT"
    SL = "STOP_LOSS"
    MANUAL = "MANUAL"
    SIGNAL = "OPPOSITE_SIGNAL"
    SHUTDOWN = "SHUTDOWN"


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), default="XAU/USD", index=True)
    side: Mapped[TradeSide] = mapped_column(SAEnum(TradeSide), nullable=False)
    status: Mapped[TradeStatus] = mapped_column(
        SAEnum(TradeStatus), default=TradeStatus.OPEN, nullable=False, index=True
    )

    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)

    size: Mapped[float] = mapped_column(Float, nullable=False)  # units (oz)
    risk_amount: Mapped[float] = mapped_column(Float, nullable=False)  # USD risk
    leverage: Mapped[int] = mapped_column(Integer, default=500)
    notional: Mapped[float] = mapped_column(Float, default=0.0)  # entry_price * size
    margin_used: Mapped[float] = mapped_column(Float, default=0.0)  # notional / leverage
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy: Mapped[str] = mapped_column(String(64), default="ema_crossover")
    timeframe: Mapped[str] = mapped_column(String(8), default="1m")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_reason: Mapped[CloseReason | None] = mapped_column(SAEnum(CloseReason), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chart_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    analysis: Mapped["TradeAnalysis | None"] = relationship(
        "TradeAnalysis", back_populates="trade", uselist=False, cascade="all, delete-orphan"
    )


class TradeAnalysis(Base):
    __tablename__ = "trade_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("trades.id", ondelete="CASCADE"), unique=True, index=True
    )

    phase: Mapped[str] = mapped_column(String(16), default="post")  # pre | post
    provider: Mapped[str] = mapped_column(String(32), default="stub")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    improvements: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    trade: Mapped["Trade"] = relationship("Trade", back_populates="analysis")
