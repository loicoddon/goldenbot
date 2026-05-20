import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

CHANNEL_PRICE = "goldenbot:price"
CHANNEL_TRADE = "goldenbot:trade"
CHANNEL_ALERT = "goldenbot:alert"
CHANNEL_PORTFOLIO = "goldenbot:portfolio"
CHANNEL_NEWS = "goldenbot:news"


class RedisBus:
    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("RedisBus not connected. Call connect() first.")
        return self._client

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        await self.client.publish(channel, json.dumps(payload, default=str))

    def pubsub(self) -> aioredis.client.PubSub:
        return self.client.pubsub()


bus = RedisBus()
