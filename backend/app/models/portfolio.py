from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Portfolio(Base):
    """Singleton row tracking the virtual portfolio state."""

    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False)  # cash (closed PnL)
    equity: Mapped[float] = mapped_column(Float, nullable=False)  # balance + unrealized PnL
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    peak_equity: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), default="XAU/USD", index=True)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
