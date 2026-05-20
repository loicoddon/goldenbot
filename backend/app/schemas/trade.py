from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TradeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    side: str
    status: str
    entry_price: float
    exit_price: float | None
    stop_loss: float
    take_profit: float
    size: float
    risk_amount: float
    leverage: int
    notional: float
    margin_used: float
    pnl: float | None
    pnl_pct: float | None
    confidence_score: float | None
    strategy: str
    timeframe: str
    reason: str | None
    close_reason: str | None
    opened_at: datetime
    closed_at: datetime | None


class TradeOut(TradeBase):
    id: int


class TradeAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_id: int
    phase: str
    provider: str
    quality_score: float | None
    confidence_score: float | None
    summary: str | None
    improvements: str | None
    created_at: datetime
