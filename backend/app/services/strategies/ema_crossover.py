"""EMA crossover with ATR-based SL/TP and RSI gating."""

from __future__ import annotations

from app.services.strategies.base import BaseStrategy, StrategySignal, atr, ema, rsi


class EmaCrossoverStrategy(BaseStrategy):
    name = "ema_crossover"

    def __init__(
        self,
        fast: int = 9,
        slow: int = 21,
        atr_period: int = 14,
        rsi_period: int = 14,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 2.5,
        buffer_size: int = 300,
    ) -> None:
        super().__init__(buffer_size=buffer_size)
        self.fast = fast
        self.slow = slow
        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self._prev_fast: float | None = None
        self._prev_slow: float | None = None

    def evaluate(self) -> StrategySignal | None:
        if len(self.bars) < self.slow + 2:
            return None
        bars = list(self.bars)
        closes = [b.close for b in bars]

        fast_ema = ema(closes[-self.slow * 2 :], self.fast)
        slow_ema = ema(closes[-self.slow * 2 :], self.slow)
        a = atr(bars, self.atr_period)
        r = rsi(closes, self.rsi_period)

        price = closes[-1]
        prev_fast = self._prev_fast
        prev_slow = self._prev_slow
        self._prev_fast, self._prev_slow = fast_ema, slow_ema

        if prev_fast is None or prev_slow is None or a <= 0:
            return None

        crossed_up = prev_fast <= prev_slow and fast_ema > slow_ema
        crossed_down = prev_fast >= prev_slow and fast_ema < slow_ema

        if crossed_up and r < 75:
            conf = self._confidence(fast_ema, slow_ema, r, a, price, "BUY")
            return StrategySignal(
                direction="BUY",
                price=price,
                confidence=conf,
                stop_loss=price - a * self.sl_atr_mult,
                take_profit=price + a * self.tp_atr_mult,
                reason=f"EMA{self.fast} crossed above EMA{self.slow}, RSI={r:.1f}",
                indicators={"ema_fast": fast_ema, "ema_slow": slow_ema, "atr": a, "rsi": r},
                strategy=self.name,
            )
        if crossed_down and r > 25:
            conf = self._confidence(fast_ema, slow_ema, r, a, price, "SELL")
            return StrategySignal(
                direction="SELL",
                price=price,
                confidence=conf,
                stop_loss=price + a * self.sl_atr_mult,
                take_profit=price - a * self.tp_atr_mult,
                reason=f"EMA{self.fast} crossed below EMA{self.slow}, RSI={r:.1f}",
                indicators={"ema_fast": fast_ema, "ema_slow": slow_ema, "atr": a, "rsi": r},
                strategy=self.name,
            )
        return None

    def _confidence(self, fast_ema, slow_ema, r, a, price, direction) -> float:
        spread = abs(fast_ema - slow_ema) / max(price, 1e-9)
        spread_score = min(spread * 5000, 40)
        if direction == "BUY":
            rsi_score = max(0.0, 40 - abs(r - 55)) / 40 * 30
        else:
            rsi_score = max(0.0, 40 - abs(r - 45)) / 40 * 30
        atr_score = min(a / max(price, 1e-9) * 10000, 30)
        return float(min(100.0, spread_score + rsi_score + atr_score))
