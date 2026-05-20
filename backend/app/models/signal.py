from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), default="XAU/USD", index=True)
    timeframe: Mapped[str] = mapped_column(String(8), default="1m")
    strategy: Mapped[str] = mapped_column(String(64), default="ema_crossover")
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY | SELL | HOLD
    price: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    accepted: Mapped[bool] = mapped_column(default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    indicators: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
