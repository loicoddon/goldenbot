"""OANDA v20 streaming + REST fallback.

Endpoints:
- Stream: GET /v3/accounts/{accountID}/pricing/stream?instruments=XAU_USD
  (line-delimited JSON, PRICE and HEARTBEAT events)
- REST poll: GET /v3/accounts/{accountID}/pricing?instruments=XAU_USD

Auth: Authorization: Bearer <api_key>
Domains: api-fxpractice / stream-fxpractice for demo; api-fxtrade / stream-fxtrade for live.

OANDA uses XAU_USD (underscore). We expose canonical XAU/USD via the base _emit.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import httpx
from loguru import logger

from app.config import settings
from app.services.feeds.base import BasePriceFeed

OANDA_INSTRUMENT = "XAU_USD"


def _hosts(env: str) -> tuple[str, str]:
    if env.lower() == "live":
        return "https://api-fxtrade.oanda.com", "https://stream-fxtrade.oanda.com"
    return "https://api-fxpractice.oanda.com", "https://stream-fxpractice.oanda.com"


class OandaFeed(BasePriceFeed):
    name = "oanda"

    async def _run(self) -> None:
        if not (settings.oanda_api_key and settings.oanda_account_id):
            logger.warning("OANDA credentials missing — feed will not run")
            return
        try:
            await self._stream_loop()
        except Exception as e:
            logger.warning("OANDA stream ended ({}), falling back to REST polling", e)
            await self._rest_poll_loop()

    async def _stream_loop(self) -> None:
        _, stream_host = _hosts(settings.oanda_env)
        url = f"{stream_host}/v3/accounts/{settings.oanda_account_id}/pricing/stream"
        headers = {"Authorization": f"Bearer {settings.oanda_api_key}"}
        params = {"instruments": OANDA_INSTRUMENT}

        backoff = 2
        while not self._stopping.is_set():
            try:
                async with httpx.AsyncClient(timeout=None, headers=headers) as client:
                    async with client.stream("GET", url, params=params) as resp:
                        if resp.status_code != 200:
                            body = await resp.aread()
                            raise RuntimeError(
                                f"OANDA stream HTTP {resp.status_code}: {body.decode()[:200]}"
                            )
                        logger.info("OANDA stream subscribed to {}", OANDA_INSTRUMENT)
                        backoff = 2  # reset
                        async for line in resp.aiter_lines():
                            if self._stopping.is_set():
                                return
                            if not line:
                                continue
                            await self._handle_line(line)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("OANDA stream error: {} — reconnect in {}s", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(60, backoff * 2)

    async def _handle_line(self, line: str) -> None:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return
        if data.get("type") != "PRICE":
            return  # ignore HEARTBEAT, etc.
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        if not bids or not asks:
            return
        try:
            bid = float(bids[0]["price"])
            ask = float(asks[0]["price"])
        except (KeyError, ValueError, TypeError):
            return
        mid = (bid + ask) / 2
        ts_str = data.get("time")
        ts = None
        if ts_str:
            try:
                # OANDA timestamps have nanosecond precision, e.g. "2024-...Z" or with offset
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").split(".")[0] + "+00:00")
            except ValueError:
                ts = None
        await self._emit(mid, ts=ts, bid=bid, ask=ask)

    async def _rest_poll_loop(self) -> None:
        rest_host, _ = _hosts(settings.oanda_env)
        url = f"{rest_host}/v3/accounts/{settings.oanda_account_id}/pricing"
        headers = {"Authorization": f"Bearer {settings.oanda_api_key}"}
        params = {"instruments": OANDA_INSTRUMENT}
        interval = 2.0
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            while not self._stopping.is_set():
                try:
                    r = await client.get(url, params=params)
                    r.raise_for_status()
                    payload = r.json()
                    for price_obj in payload.get("prices") or []:
                        bids = price_obj.get("bids") or []
                        asks = price_obj.get("asks") or []
                        if not bids or not asks:
                            continue
                        bid = float(bids[0]["price"])
                        ask = float(asks[0]["price"])
                        await self._emit((bid + ask) / 2, bid=bid, ask=ask)
                except Exception as e:
                    logger.warning("OANDA REST error: {}", e)
                await asyncio.sleep(interval)
