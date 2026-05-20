"""Strategy base classes shared by all implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

Direction = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Bar:
    open: float
    high: float
    low: float
    close: float


@dataclass
class StrategySignal:
    direction: Direction
    price: float
    confidence: float
    stop_loss: float
    take_profit: float
    reason: str
    indicators: dict = field(default_factory=dict)
    strategy: str = ""


class BaseStrategy(ABC):
    name: str = "base"

    def __init__(self, buffer_size: int = 300) -> None:
        self.bars: deque[Bar] = deque(maxlen=buffer_size)

    def add_bar(self, bar: Bar) -> None:
        self.bars.append(bar)

    @abstractmethod
    def evaluate(self) -> StrategySignal | None:
        """Return a signal if the strategy fires on the latest bar."""


# ---- Shared indicator helpers ----

def ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    if len(values) < period:
        return float(np.mean(values))
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return float(e)


def atr(bars: list[Bar], period: int) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    prev_close = bars[0].close
    for b in bars[1:]:
        tr = max(b.high - b.low, abs(b.high - prev_close), abs(b.low - prev_close))
        trs.append(tr)
        prev_close = b.close
    if not trs:
        return 0.0
    return float(np.mean(trs[-period:]))


def rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


# ---- Tick → bar aggregator (kept here for reuse) ----

class BarAggregator:
    def __init__(self, timeframe_seconds: int = 60) -> None:
        self.tf = timeframe_seconds
        self._current: Bar | None = None
        self._bucket_start: int | None = None

    def add_tick(self, price: float, ts_epoch: int) -> Bar | None:
        bucket = (ts_epoch // self.tf) * self.tf
        if self._bucket_start is None:
            self._bucket_start = bucket
            self._current = Bar(open=price, high=price, low=price, close=price)
            return None
        if bucket == self._bucket_start:
            assert self._current
            self._current.high = max(self._current.high, price)
            self._current.low = min(self._current.low, price)
            self._current.close = price
            return None
        closed = self._current
        self._bucket_start = bucket
        self._current = Bar(open=price, high=price, low=price, close=price)
        return closed
