"""Correlated markets feed — DXY, US10Y, WTI oil, S&P500.

Polls TwelveData REST every CORRELATED_POLL_INTERVAL seconds. Maintains
in-memory cache for fast lookup by IA agents. Persisted into price_ticks too
so the backtest engine and history endpoints can use them.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from app.config import settings
from app.database import SessionLocal
from app.models.price import PriceTick

CORRELATED_SYMBOLS = ["DXY", "TNX", "WTI/USD", "SPX"]
TD_REST_URL = "https://api.twelvedata.com/price"


class CorrelatedFeed:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._cache: dict[str, dict[str, Any]] = {}
        # Interval is hardcoded conservative — 30s is fine for context purposes
        self._interval: float = 30.0

    @property
    def snapshot(self) -> dict[str, Any]:
        return {sym: data.copy() for sym, data in self._cache.items()}

    async def start(self) -> None:
        if not settings.correlated_feed_enabled:
            logger.info("Correlated feed disabled by config (CORRELATED_FEED_ENABLED=false)")
            return
        if not settings.twelvedata_api_key:
            logger.warning("Correlated feed disabled (no TwelveData key)")
            return
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="correlated_feed")
        logger.info("CorrelatedFeed started for {}", ", ".join(CORRELATED_SYMBOLS))

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._poll()
            except Exception as e:
                logger.warning("Correlated poll error: {}", e)
            await asyncio.sleep(self._interval)

    async def _poll(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            for sym in CORRELATED_SYMBOLS:
                try:
                    r = await client.get(
                        TD_REST_URL,
                        params={"symbol": sym, "apikey": settings.twelvedata_api_key},
                    )
                    if r.status_code != 200:
                        logger.warning(
                            "Correlated {} HTTP {}: {}",
                            sym, r.status_code, r.text[:200],
                        )
                        continue
                    data = r.json()
                    if isinstance(data, dict) and data.get("status") == "error":
                        logger.warning(
                            "Correlated {} API error: {}",
                            sym, data.get("message", "?")[:200],
                        )
                        continue
                    price = data.get("price")
                    if price is None:
                        logger.warning("Correlated {} payload has no price: {}", sym, str(data)[:200])
                        continue
                    price = float(price)
                except Exception as e:
                    logger.warning("Correlated fetch {} failed: {}", sym, e)
                    continue
                ts = datetime.utcnow()
                prev = self._cache.get(sym, {}).get("price")
                change_pct = (
                    (price - prev) / prev * 100 if prev not in (None, 0) else 0.0
                )
                self._cache[sym] = {
                    "symbol": sym,
                    "price": price,
                    "change_pct": change_pct,
                    "timestamp": ts.isoformat(),
                }
                try:
                    async with SessionLocal() as session:
                        session.add(PriceTick(symbol=sym, price=price, timestamp=ts))
                        await session.commit()
                except Exception as e:
                    logger.debug("Tick persist {} failed: {}", sym, e)


correlated_feed = CorrelatedFeed()
