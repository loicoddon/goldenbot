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
        # Re-calibrated for high-price assets (gold ~$4500): the previous
        # formula's *10000 factor on atr/price plafonné at ~5/30 for gold
        # because its relative volatility (~0.04%) is much smaller than
        # the assumed stock baseline (~0.25%). We now use percent units
        # with a sigmoid-ish piecewise so atr_score saturates ~30 at the
        # typical gold scalping volatility.
        spread_pct = abs(fast_ema - slow_ema) / max(price, 1e-9) * 100  # %
        # Spread at the crossover is naturally small. Scale generously.
        spread_score = min(spread_pct * 800, 30)

        atr_pct = a / max(price, 1e-9) * 100  # %
        # Gold typical 1m ATR ~0.04-0.10%, stocks 0.1-0.5%. Scale gives
        # decent score on gold low-vol and saturates fast.
        if atr_pct < 0.02:
            atr_score = atr_pct / 0.02 * 15
        elif atr_pct < 0.05:
            atr_score = 15 + (atr_pct - 0.02) / 0.03 * 15  # 15..30
        elif atr_pct < 0.10:
            atr_score = 30 + (atr_pct - 0.05) / 0.05 * 10  # 30..40
        else:
            atr_score = 40

        if direction == "BUY":
            rsi_score = max(0.0, 40 - abs(r - 55)) / 40 * 30
        else:
            rsi_score = max(0.0, 40 - abs(r - 45)) / 40 * 30

        return float(min(100.0, spread_score + atr_score + rsi_score))
