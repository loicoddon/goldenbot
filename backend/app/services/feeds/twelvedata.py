"""TwelveData WebSocket + REST polling + mock fallback."""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import websockets
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.services.feeds.base import BasePriceFeed

WS_URL = "wss://ws.twelvedata.com/v1/quotes/price?apikey={api_key}"
REST_URL = "https://api.twelvedata.com/price"


class TwelveDataFeed(BasePriceFeed):
    name = "twelvedata"

    # REST fallback runs for at most this long, then _run returns so the
    # supervisor restarts it and we retry the (quota-free) WebSocket.
    REST_FALLBACK_WINDOW_S = 300

    async def _run(self) -> None:
        if not settings.twelvedata_api_key:
            logger.warning("TWELVEDATA_API_KEY missing — running in MOCK mode")
            await self._mock_loop()
            return
        try:
            await self._ws_loop()
        except Exception as e:
            logger.warning("TwelveData WS ended ({}), falling back to REST polling", e)
            await self._rest_poll_loop()
        # _run returns here on either WS or REST exit. The supervised wrapper
        # in BasePriceFeed restarts _run() after a short delay, so we always
        # cycle back to attempting the WebSocket (which doesn't consume the
        # daily REST quota). Previously the REST loop was infinite, leaving
        # the feed permanently in REST mode burning quota even after WS
        # service recovered.

    async def _ws_loop(self) -> None:
        url = WS_URL.format(api_key=settings.twelvedata_api_key)
        symbol = settings.twelvedata_symbol
        async for attempt in AsyncRetrying(
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(5),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                async with websockets.connect(url, ping_interval=20) as ws:
                    await ws.send(json.dumps({"action": "subscribe", "params": {"symbols": symbol}}))
                    logger.info("TwelveData WS subscribed to {}", symbol)
                    while not self._stopping.is_set():
                        msg = await asyncio.wait_for(ws.recv(), timeout=60)
                        await self._handle_ws_msg(msg)

    async def _handle_ws_msg(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        event = data.get("event")
        if event == "price":
            try:
                price = float(data["price"])
            except (KeyError, ValueError, TypeError):
                return
            await self._emit(price)
        elif event in ("subscribe-status", "heartbeat", None):
            return  # quiet expected events
        else:
            logger.warning("TwelveData WS unexpected payload: {}", str(data)[:200])

    async def _rest_poll_loop(self) -> None:
        symbol = settings.twelvedata_symbol
        interval = max(settings.twelvedata_poll_interval, 1.0)
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=10) as client:
            while not self._stopping.is_set():
                # Time-box the REST window so _run() returns and the supervisor
                # retries the WebSocket (which doesn't burn the REST quota).
                if time.monotonic() - started > self.REST_FALLBACK_WINDOW_S:
                    logger.info("REST window elapsed — returning to retry WebSocket")
                    return
                try:
                    r = await client.get(
                        REST_URL,
                        params={"symbol": symbol, "apikey": settings.twelvedata_api_key},
                    )
                    r.raise_for_status()
                    data = r.json()
                    # TwelveData returns HTTP 200 with {"code": 429, ...} on quota
                    # exhaustion and other API errors, so r.raise_for_status() misses them.
                    if isinstance(data, dict) and (
                        data.get("status") == "error"
                        or data.get("code") in (400, 401, 403, 429, 500)
                    ):
                        code = data.get("code", "?")
                        msg = str(data.get("message", ""))[:200]
                        logger.warning("TwelveData REST API error code={} msg={}", code, msg)
                        if code == 429:
                            # Quota exhausted — REST is useless until reset, but
                            # the WS doesn't need the REST quota. Bail immediately
                            # so the supervisor retries WS instead of spinning here.
                            logger.info("REST quota exhausted — returning to retry WebSocket")
                            return
                        await asyncio.sleep(10)
                        continue
                    if "price" in data:
                        await self._emit(float(data["price"]))
                except Exception as e:
                    logger.warning("TwelveData REST error: {}", e)
                await asyncio.sleep(interval)

    async def _mock_loop(self) -> None:
        import random

        price = 2380.0
        while not self._stopping.is_set():
            price = max(1500.0, min(3500.0, price + random.gauss(0, 0.4)))
            await self._emit(price)
            await asyncio.sleep(1.0)
