from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BotSettings(Base):
    """Singleton row holding live-editable bot configuration."""

    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    symbol: Mapped[str] = mapped_column(String(16), default="XAU/USD")
    timeframe: Mapped[str] = mapped_column(String(8), default="1m")
    strategy: Mapped[str] = mapped_column(String(64), default="ema_crossover")

    risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=1.0)
    daily_loss_limit_pct: Mapped[float] = mapped_column(Float, default=5.0)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=10)
    min_confidence: Mapped[float] = mapped_column(Float, default=50.0)
    leverage: Mapped[int] = mapped_column(Integer, default=500)
    # Lot size bounds (in standard lots, 1 lot = 100 oz on XAU/USD).
    # When max_lot_size > 0, size is forced into [min, max] using confidence-mapped
    # interpolation — risk_per_trade_pct is then no longer the binding constraint.
    min_lot_size: Mapped[float] = mapped_column(Float, default=0.0)
    max_lot_size: Mapped[float] = mapped_column(Float, default=0.0)

    # AI analysis frequency: every N trades (1, 3, 5, 10, 20)
    ai_analysis_every: Mapped[int] = mapped_column(Integer, default=1)
    ai_provider: Mapped[str] = mapped_column(String(16), default="stub")
    ai_pretrade_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_min_pretrade_score: Mapped[float] = mapped_column(Float, default=50.0)

    # News filter
    news_filter_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    news_block_before_min: Mapped[int] = mapped_column(Integer, default=15)
    news_block_after_min: Mapped[int] = mapped_column(Integer, default=15)

    # Optimizer
    optimizer_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    optimizer_window_trades: Mapped[int] = mapped_column(Integer, default=20)
    optimizer_run_every_trades: Mapped[int] = mapped_column(Integer, default=10)

    # Multi-position + session adaptation
    max_open_positions: Mapped[int] = mapped_column(Integer, default=1)
    session_min_confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Multi-strategy registry: list of strategy names, configurable weights
    strategies_enabled: Mapped[list | None] = mapped_column(JSON, nullable=True)
    strategy_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Multi-IA voting
    multi_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_agent_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
