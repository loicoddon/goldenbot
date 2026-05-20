"""Wyckoff-style strategy — simplified spring / upthrust detection.

Steps:
1. Identify a range (consolidation) over the last N bars where the high-low
   spread is narrow relative to ATR.
2. Detect Spring: a bar pierces below the range low then closes back inside.
3. Detect Upthrust: a bar pierces above the range high then closes back inside.
4. Generate signal on the bar following confirmation.
"""

from __future__ import annotations

from app.services.strategies.base import BaseStrategy, StrategySignal, atr


class WyckoffStrategy(BaseStrategy):
    name = "wyckoff"

    def __init__(
        self,
        range_lookback: int = 20,
        range_max_atr_mult: float = 3.0,
        atr_period: int = 14,
        sl_atr_mult: float = 1.0,
        tp_atr_mult: float = 2.0,
        buffer_size: int = 400,
    ) -> None:
        super().__init__(buffer_size=buffer_size)
        self.range_lookback = range_lookback
        self.range_max_atr_mult = range_max_atr_mult
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def evaluate(self) -> StrategySignal | None:
        if len(self.bars) < self.range_lookback + 2:
            return None
        bars = list(self.bars)
        a = atr(bars, self.atr_period)
        if a <= 0:
            return None
        window = bars[-(self.range_lookback + 1) : -1]
        range_high = max(b.high for b in window)
        range_low = min(b.low for b in window)
        range_size = range_high - range_low
        if range_size > self.range_max_atr_mult * a:
            return None  # not a tight range

        last = bars[-1]
        price = last.close

        # Spring: pierces below range_low then closes back inside
        spring = last.low < range_low and last.close > range_low
        # Upthrust: pierces above range_high then closes back inside
        upthrust = last.high > range_high and last.close < range_high

        if spring:
            confidence = self._confidence("BUY", a, price, range_size, last)
            sl = last.low - a * 0.2
            tp = price + a * self.tp_atr_mult
            return StrategySignal(
                direction="BUY",
                price=price,
                confidence=confidence,
                stop_loss=sl,
                take_profit=tp,
                reason=(
                    f"Wyckoff spring: pierced {range_low:.2f}, closed back at {price:.2f}"
                ),
                indicators={
                    "range_low": range_low,
                    "range_high": range_high,
                    "range_size": range_size,
                    "atr": a,
                },
                strategy=self.name,
            )
        if upthrust:
            confidence = self._confidence("SELL", a, price, range_size, last)
            sl = last.high + a * 0.2
            tp = price - a * self.tp_atr_mult
            return StrategySignal(
                direction="SELL",
                price=price,
                confidence=confidence,
                stop_loss=sl,
                take_profit=tp,
                reason=(
                    f"Wyckoff upthrust: pierced {range_high:.2f}, closed back at {price:.2f}"
                ),
                indicators={
                    "range_low": range_low,
                    "range_high": range_high,
                    "range_size": range_size,
                    "atr": a,
                },
                strategy=self.name,
            )
        return None

    def _confidence(self, kind: str, a: float, price: float, range_size: float, last) -> float:
        # Penetration depth scoring (deeper sweep = stronger signal)
        if kind == "BUY":
            penetration = abs(last.low - price) / max(a, 1e-9)
        else:
            penetration = abs(last.high - price) / max(a, 1e-9)
        depth_score = min(40.0, penetration * 40)
        tightness_score = max(0.0, 30 - (range_size / max(a, 1e-9)) * 10)
        body_score = abs(last.close - last.open) / max(a, 1e-9) * 30
        return float(min(100.0, depth_score + tightness_score + body_score))
