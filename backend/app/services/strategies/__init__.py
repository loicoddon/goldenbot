"""Strategy registry — pluggable trading strategies.

Each strategy implements BaseStrategy and is registered here.
The engine instantiates one per enabled strategy and feeds each new bar.
"""

from __future__ import annotations

from app.services.strategies.base import BarAggregator, BaseStrategy, StrategySignal
from app.services.strategies.ema_crossover import EmaCrossoverStrategy
from app.services.strategies.smc import SmcStrategy
from app.services.strategies.wyckoff import WyckoffStrategy

REGISTRY: dict[str, type[BaseStrategy]] = {
    EmaCrossoverStrategy.name: EmaCrossoverStrategy,
    SmcStrategy.name: SmcStrategy,
    WyckoffStrategy.name: WyckoffStrategy,
}


def get_strategy(name: str, **kwargs) -> BaseStrategy:
    cls = REGISTRY.get(name, EmaCrossoverStrategy)
    return cls(**kwargs)


def available_strategies() -> list[str]:
    return list(REGISTRY.keys())


__all__ = [
    "BarAggregator",
    "BaseStrategy",
    "EmaCrossoverStrategy",
    "REGISTRY",
    "SmcStrategy",
    "StrategySignal",
    "WyckoffStrategy",
    "available_strategies",
    "get_strategy",
]
