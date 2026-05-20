from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreate(BaseModel):
    symbol: str = "XAU/USD"
    strategy: str = "ema_crossover"
    timeframe: str = "1m"
    initial_capital: float = Field(default=1000.0, gt=0)
    leverage: int = Field(default=500, ge=1, le=2000)
    risk_per_trade_pct: float = Field(default=1.0, ge=0.1, le=10.0)
    from_ts: datetime
    to_ts: datetime
    params: dict[str, Any] | None = None


class BacktestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    strategy: str
    timeframe: str
    initial_capital: float
    leverage: int
    risk_per_trade_pct: float
    params: dict[str, Any] | None
    from_ts: datetime
    to_ts: datetime
    status: str
    error: str | None
    final_equity: float | None
    total_return_pct: float | None
    sharpe: float | None
    profit_factor: float | None
    max_drawdown_pct: float | None
    winrate: float | None
    expectancy: float | None
    total_trades: int | None
    started_at: datetime
    finished_at: datetime | None


class BacktestDetailOut(BacktestOut):
    trades: list[dict[str, Any]] | None
    equity_curve: list[dict[str, Any]] | None
