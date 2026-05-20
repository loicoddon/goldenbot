"""Failover wrapper: primary feed + automatic switch to secondary on staleness.

Only one backend runs at a time. The monitor task checks `last_timestamp`
of the active backend every 20s; if it's been silent > 60s, the wrapper stops
it and starts the other one. No auto-revert (keeps the secondary until the
process restarts — manual intervention via /api/feed/restart).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger

from app.services.feeds.base import BasePriceFeed, PriceListener

STALE_S = 60
CHECK_EVERY_S = 20


class FailoverPriceFeed:
    name = "failover"

    def __init__(self, *, primary: BasePriceFeed, secondary: BasePriceFeed) -> None:
        self._primary = primary
        self._secondary = secondary
        self._active: BasePriceFeed | None = None
        self._monitor_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def active_name(self) -> str:
        return self._active.name if self._active else "none"

    @property
    def last_price(self):
        return self._active.last_price if self._active else None

    @property
    def last_timestamp(self):
        return self._active.last_timestamp if self._active else None

    def subscribe(self, listener: PriceListener) -> None:
        # Register on both so switching is transparent — only the active one fires.
        self._primary.subscribe(listener)
        self._secondary.subscribe(listener)

    async def start(self) -> None:
        async with self._lock:
            await self._try_start(self._primary)
            if self._active is None:
                await self._try_start(self._secondary)
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor(), name="feed_monitor")

    async def stop(self) -> None:
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except (asyncio.CancelledError, Exception):
                pass
            self._monitor_task = None
        await self._primary.stop()
        await self._secondary.stop()

    async def restart(self) -> None:
        """Manual reset: stop both, start primary again."""
        await self.stop()
        await self.start()

    async def _try_start(self, feed: BasePriceFeed) -> bool:
        try:
            await feed.start()
            self._active = feed
            logger.info("Feed active: {}", feed.name)
            return True
        except Exception as e:
            logger.warning("Feed {} failed to start: {}", feed.name, e)
            return False

    async def _monitor(self) -> None:
        while True:
            try:
                await asyncio.sleep(CHECK_EVERY_S)
            except asyncio.CancelledError:
                return
            now = datetime.now(timezone.utc)
            active = self._active
            if active is None:
                logger.warning("No active feed — attempting restart")
                async with self._lock:
                    if not await self._try_start(self._primary):
                        await self._try_start(self._secondary)
                continue
            last_ts = active.last_timestamp
            if last_ts is not None and last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            age = (now - last_ts).total_seconds() if last_ts else float("inf")
            if age > STALE_S:
                other = self._secondary if active is self._primary else self._primary
                logger.warning(
                    "Active feed {} stale ({:.0f}s) — switching to {}",
                    active.name, age, other.name,
                )
                async with self._lock:
                    try:
                        await active.stop()
                    except Exception:
                        pass
                    self._active = None
                    if not await self._try_start(other):
                        logger.error("Failover target {} also failed", other.name)


__all__ = ["FailoverPriceFeed"]
