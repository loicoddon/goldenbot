from pydantic import BaseModel, ConfigDict, Field


class BotSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    symbol: str
    timeframe: str
    strategy: str
    risk_per_trade_pct: float
    daily_loss_limit_pct: float
    max_trades_per_day: int
    min_confidence: float
    leverage: int
    min_lot_size: float
    max_lot_size: float
    confidence_for_max_lot: float
    confidence_skip_low: float
    confidence_skip_high: float
    ai_analysis_every: int
    ai_provider: str
    ai_pretrade_enabled: bool
    ai_min_pretrade_score: float
    news_filter_enabled: bool
    news_block_before_min: int
    news_block_after_min: int
    optimizer_enabled: bool
    optimizer_window_trades: int
    optimizer_run_every_trades: int
    max_open_positions: int
    session_min_confidence: dict | None
    strategies_enabled: list | None
    strategy_weights: dict | None
    multi_ai_enabled: bool
    ai_agent_weights: dict | None


class BotSettingsUpdate(BaseModel):
    enabled: bool | None = None
    timeframe: str | None = None
    strategy: str | None = None
    risk_per_trade_pct: float | None = Field(default=None, ge=0.1, le=10.0)
    daily_loss_limit_pct: float | None = Field(default=None, ge=0.5, le=50.0)
    max_trades_per_day: int | None = Field(default=None, ge=1, le=200)
    min_confidence: float | None = Field(default=None, ge=0.0, le=100.0)
    leverage: int | None = Field(default=None, ge=1, le=2000)
    min_lot_size: float | None = Field(default=None, ge=0.0, le=10.0)
    max_lot_size: float | None = Field(default=None, ge=0.0, le=10.0)
    confidence_for_max_lot: float | None = Field(default=None, ge=10.0, le=100.0)
    confidence_skip_low: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence_skip_high: float | None = Field(default=None, ge=0.0, le=100.0)
    ai_analysis_every: int | None = Field(default=None, ge=1, le=100)
    ai_provider: str | None = None
    ai_pretrade_enabled: bool | None = None
    ai_min_pretrade_score: float | None = Field(default=None, ge=0.0, le=100.0)
    news_filter_enabled: bool | None = None
    news_block_before_min: int | None = Field(default=None, ge=0, le=120)
    news_block_after_min: int | None = Field(default=None, ge=0, le=120)
    optimizer_enabled: bool | None = None
    optimizer_window_trades: int | None = Field(default=None, ge=5, le=200)
    optimizer_run_every_trades: int | None = Field(default=None, ge=1, le=100)
    max_open_positions: int | None = Field(default=None, ge=1, le=20)
    session_min_confidence: dict | None = None
    strategies_enabled: list | None = None
    strategy_weights: dict | None = None
    multi_ai_enabled: bool | None = None
    ai_agent_weights: dict | None = None
