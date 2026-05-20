from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initial_capital: float
    balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    peak_equity: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    updated_at: datetime


class PortfolioStats(BaseModel):
    winrate: float
    expectancy: float
    profit_factor: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float


class EquityPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    balance: float
    equity: float
    drawdown_pct: float
