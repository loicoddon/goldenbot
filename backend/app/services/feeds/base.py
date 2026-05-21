"""Base class for price-feed backends.

A backend owns its own connection (WS / streaming / polling) and emits ticks via
`_emit`. The base class handles persistence (DB + price_ticks), Redis pub/sub,
and listener notification, so each backend just needs to call `await self._emit(price, ts, bid, ask)`.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.config import settings
from app.core.redis_bus import CHANNEL_PRICE, bus
from app.database import SessionLocal
from app.models.price import PriceTick

PriceListener = Callable[[dict[str, Any]], "asyncio.Future[Any] | None"]


class BasePriceFeed(ABC):
    name: str = "base"
    _restart_delay_s: int = 30

    def __init__(self) -> None:
        self._listeners: list[PriceListener] = []
        self._last_price: float | None = None
        self._last_ts: datetime | None = None
        self._stopping = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def last_price(self) -> float | None:
        return self._last_price

    @property
    def last_timestamp(self) -> datetime | None:
        return self._last_ts

    def subscribe(self, listener: PriceListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    @abstractmethod
    async def _run(self) -> None:
        """Backend-specific loop. Must call `_emit` on each tick."""

    async def _supervised_run(self) -> None:
        """Wrap _run so a clean exit or crash auto-restarts after a delay.

        Without this, a single transient failure (network glitch, quota error,
        WS server reset) leaves the feed silently dead until manual restart.
        """
        while not self._stopping.is_set():
            try:
                await self._run()
                if self._stopping.is_set():
                    return
                logger.warning(
                    "Feed {} loop ended cleanly — restarting in {}s",
                    self.name, self._restart_delay_s,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Feed {} crashed: {} — restarting in {}s",
                    self.name, e, self._restart_delay_s,
                )
            try:
                await asyncio.sleep(self._restart_delay_s)
            except asyncio.CancelledError:
                raise

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._supervised_run(), name=f"feed_{self.name}")
        logger.info("Feed {} started (supervised, auto-restart on failure)", self.name)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("Feed {} stopped", self.name)

    async def _emit(
        self,
        price: float,
        ts: datetime | None = None,
        bid: float | None = None,
        ask: float | None = None,
    ) -> None:
        ts = ts or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        self._last_price = price
        self._last_ts = ts
        symbol = settings.twelvedata_symbol  # canonical "XAU/USD" used in DB

        try:
            async with SessionLocal() as session:
                session.add(
                    PriceTick(symbol=symbol, price=price, bid=bid, ask=ask, timestamp=ts)
                )
                await session.commit()
        except Exception as e:
            logger.warning("Tick persist failed: {}", e)

        payload = {
            "symbol": symbol,
            "price": price,
            "bid": bid,
            "ask": ask,
            "timestamp": ts.isoformat(),
            "source": self.name,
        }
        try:
            await bus.publish(CHANNEL_PRICE, payload)
        except Exception as e:
            logger.warning("Tick publish failed: {}", e)

        for fn in self._listeners:
            try:
                coro = fn(payload)
                if asyncio.iscoroutine(coro):
                    asyncio.create_task(coro)
            except Exception as e:
                logger.exception("Listener error: {}", e)
