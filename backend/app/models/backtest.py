from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Enum as SAEnum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), default="XAU/USD")
    strategy: Mapped[str] = mapped_column(String(64), default="ema_crossover")
    timeframe: Mapped[str] = mapped_column(String(8), default="1m")
    initial_capital: Mapped[float] = mapped_column(Float, default=1000.0)
    leverage: Mapped[int] = mapped_column(Integer, default=500)
    risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=1.0)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    from_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    status: Mapped[BacktestStatus] = mapped_column(
        SAEnum(BacktestStatus), default=BacktestStatus.PENDING, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Results
    final_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    winrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Detailed payloads
    trades: Mapped[list | None] = mapped_column(JSON, nullable=True)
    equity_curve: Mapped[list | None] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
