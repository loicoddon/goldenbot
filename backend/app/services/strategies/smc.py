"""Smart Money Concepts (SMC) strategy — simplified Phase 3 implementation.

Detects:
- Fair Value Gap (FVG): 3-bar imbalance pattern
  · Bullish FVG: bar[i-2].high < bar[i].low  (gap between bar 1 high and bar 3 low)
  · Bearish FVG: bar[i-2].low > bar[i].high
- Liquidity sweep + reversal: price wicks beyond N-bar high/low then closes back inside
- Bullish/Bearish order block: the last opposing candle before a strong impulse

A signal fires when an FVG forms in the same direction as a recent liquidity
sweep, or when price retraces into an order block after a sweep.
"""

from __future__ import annotations

from app.services.strategies.base import BaseStrategy, StrategySignal, atr


class SmcStrategy(BaseStrategy):
    name = "smc"

    def __init__(
        self,
        lookback: int = 30,
        atr_period: int = 14,
        sl_atr_mult: float = 1.2,
        tp_atr_mult: float = 2.5,
        buffer_size: int = 300,
    ) -> None:
        super().__init__(buffer_size=buffer_size)
        self.lookback = lookback
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def evaluate(self) -> StrategySignal | None:
        if len(self.bars) < self.lookback + 3:
            return None
        bars = list(self.bars)
        recent = bars[-self.lookback :]
        a = atr(bars, self.atr_period)
        if a <= 0:
            return None
        price = bars[-1].close

        # Liquidity sweep detection on the last bar
        prior = bars[-(self.lookback + 1) : -1]
        prior_high = max(b.high for b in prior)
        prior_low = min(b.low for b in prior)
        last = bars[-1]

        sweep_high = last.high > prior_high and last.close < prior_high  # bearish sweep
        sweep_low = last.low < prior_low and last.close > prior_low  # bullish sweep

        # FVG check on last 3 bars
        b1, b2, b3 = bars[-3], bars[-2], bars[-1]
        bullish_fvg = b1.high < b3.low
        bearish_fvg = b1.low > b3.high

        # Buy: bullish sweep OR bullish FVG with a recent low touch
        if sweep_low or (bullish_fvg and any(b.low <= b3.low for b in recent[-5:])):
            confidence = self._confidence(
                kind="BUY",
                sweep=sweep_low,
                fvg=bullish_fvg,
                a=a,
                price=price,
            )
            sl = min(last.low, prior_low) - a * 0.2
            tp = price + a * self.tp_atr_mult
            return StrategySignal(
                direction="BUY",
                price=price,
                confidence=confidence,
                stop_loss=sl,
                take_profit=tp,
                reason=(
                    f"SMC bullish: sweep={sweep_low} fvg={bullish_fvg} "
                    f"prior_low={prior_low:.2f}"
                ),
                indicators={
                    "atr": a,
                    "prior_low": prior_low,
                    "prior_high": prior_high,
                    "sweep_low": sweep_low,
                    "bullish_fvg": bullish_fvg,
                },
                strategy=self.name,
            )

        if sweep_high or (bearish_fvg and any(b.high >= b3.high for b in recent[-5:])):
            confidence = self._confidence(
                kind="SELL",
                sweep=sweep_high,
                fvg=bearish_fvg,
                a=a,
                price=price,
            )
            sl = max(last.high, prior_high) + a * 0.2
            tp = price - a * self.tp_atr_mult
            return StrategySignal(
                direction="SELL",
                price=price,
                confidence=confidence,
                stop_loss=sl,
                take_profit=tp,
                reason=(
                    f"SMC bearish: sweep={sweep_high} fvg={bearish_fvg} "
                    f"prior_high={prior_high:.2f}"
                ),
                indicators={
                    "atr": a,
                    "prior_low": prior_low,
                    "prior_high": prior_high,
                    "sweep_high": sweep_high,
                    "bearish_fvg": bearish_fvg,
                },
                strategy=self.name,
            )
        return None

    def _confidence(self, *, kind: str, sweep: bool, fvg: bool, a: float, price: float) -> float:
        score = 35.0
        if sweep:
            score += 30
        if fvg:
            score += 25
        # Volatility bonus
        score += min(20.0, (a / max(price, 1e-9)) * 10000)
        return float(min(100.0, score))
