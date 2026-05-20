"""WebSocket bridge: relays Redis pub/sub events to connected clients."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.redis_bus import (
    CHANNEL_ALERT,
    CHANNEL_PORTFOLIO,
    CHANNEL_PRICE,
    CHANNEL_TRADE,
    bus,
)

router = APIRouter()

ALL_CHANNELS = [CHANNEL_PRICE, CHANNEL_TRADE, CHANNEL_PORTFOLIO, CHANNEL_ALERT]


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = bus.pubsub()
    await pubsub.subscribe(*ALL_CHANNELS)
    logger.info("WS client connected, subscribed to {} channels", len(ALL_CHANNELS))

    async def reader():
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                channel = message["channel"]
                try:
                    data = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    data = message["data"]
                await websocket.send_json({"channel": channel, "data": data})
        except Exception as e:
            logger.warning("WS reader error: {}", e)

    task = asyncio.create_task(reader())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WS client disconnected")
    finally:
        task.cancel()
        try:
            await pubsub.unsubscribe(*ALL_CHANNELS)
            await pubsub.close()
        except Exception:
            pass
