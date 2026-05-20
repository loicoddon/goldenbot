"""GoldenBot Discord notifier.

Subscribes to Redis pub/sub channels and posts formatted messages to a
configured Discord channel.
"""

from __future__ import annotations

import asyncio
import json
import os

import discord
import redis.asyncio as aioredis
from loguru import logger

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "")
INITIAL_CAPITAL = float(os.environ.get("INITIAL_CAPITAL", "1000"))

CHANNEL_TRADE = "goldenbot:trade"
CHANNEL_ALERT = "goldenbot:alert"
CHANNEL_PORTFOLIO = "goldenbot:portfolio"


class GoldenDiscord(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self._redis: aioredis.Redis | None = None
        self._target_channel: discord.TextChannel | None = None
        self._pubsub_task: asyncio.Task | None = None
        self._portfolio: dict[str, float] = {}

    async def on_ready(self) -> None:
        logger.info("Discord bot logged in as {}", self.user)
        if not DISCORD_CHANNEL_ID:
            logger.error("DISCORD_CHANNEL_ID not set — bot will not post messages")
            return
        try:
            channel = self.get_channel(int(DISCORD_CHANNEL_ID))
            if channel is None:
                channel = await self.fetch_channel(int(DISCORD_CHANNEL_ID))
            self._target_channel = channel  # type: ignore[assignment]
            logger.info("Posting in channel #{}", channel.name if channel else DISCORD_CHANNEL_ID)
        except Exception as e:
            logger.error("Cannot resolve Discord channel {}: {}", DISCORD_CHANNEL_ID, e)
            return

        self._redis = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL_TRADE, CHANNEL_ALERT, CHANNEL_PORTFOLIO)
        logger.info("Subscribed to Redis channels")
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    data = json.loads(msg["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if msg["channel"] == CHANNEL_TRADE:
                    await self._handle_trade(data)
                elif msg["channel"] == CHANNEL_ALERT:
                    await self._handle_alert(data)
                elif msg["channel"] == CHANNEL_PORTFOLIO:
                    self._portfolio = data
        except Exception as e:
            logger.exception("Pub/sub listener crashed: {}", e)

    def _portfolio_summary(self) -> str:
        if not self._portfolio:
            return "—"
        equity = float(self._portfolio.get("equity", 0))
        realized = float(self._portfolio.get("realized_pnl", 0))
        unrealized = float(self._portfolio.get("unrealized_pnl", 0))
        dd = float(self._portfolio.get("max_drawdown_pct", 0))
        total_pnl = equity - INITIAL_CAPITAL
        ret_pct = (total_pnl / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL else 0.0
        sign = "+" if total_pnl >= 0 else ""
        lines = [
            f"**Equity:** `{equity:,.2f} $`",
            f"**Total PnL:** `{sign}{total_pnl:,.2f} $ ({sign}{ret_pct:+.2f}%)`",
            f"**Realized / Unrealized:** `{realized:+.2f} / {unrealized:+.2f} $`",
            f"**Max DD:** `{dd:.2f}%`",
        ]
        return "\n".join(lines)

    async def _handle_trade(self, data: dict) -> None:
        if not self._target_channel:
            return
        event = data.get("event")
        trade = data.get("trade", {})
        if event == "open":
            side = trade.get("side", "?")
            color = 0x2ECC71 if side == "BUY" else 0xE74C3C
            embed = discord.Embed(
                title=f":chart_with_upwards_trend: TRADE OPEN — {side} XAU/USD",
                color=color,
            )
            embed.add_field(name="Entry", value=f"{trade.get('entry_price', 0):.2f}", inline=True)
            embed.add_field(name="SL", value=f"{trade.get('stop_loss', 0):.2f}", inline=True)
            embed.add_field(name="TP", value=f"{trade.get('take_profit', 0):.2f}", inline=True)
            embed.add_field(name="Size", value=f"{trade.get('size', 0):.4f}", inline=True)
            embed.add_field(
                name="Confidence", value=f"{trade.get('confidence', 0):.1f}/100", inline=True
            )
            embed.add_field(name="Reason", value=trade.get("reason", "n/a"), inline=False)
            embed.add_field(name="📊 Portfolio", value=self._portfolio_summary(), inline=False)
            await self._target_channel.send(embed=embed)
        elif event == "close":
            pnl = trade.get("pnl", 0)
            won = pnl > 0
            color = 0x2ECC71 if won else 0xE74C3C
            title_emoji = ":white_check_mark:" if won else ":x:"
            embed = discord.Embed(
                title=f"{title_emoji} TRADE CLOSED — {trade.get('side', '?')} XAU/USD",
                color=color,
            )
            embed.add_field(name="Entry", value=f"{trade.get('entry_price', 0):.2f}", inline=True)
            embed.add_field(name="Exit", value=f"{trade.get('exit_price', 0):.2f}", inline=True)
            embed.add_field(
                name="PnL",
                value=f"{pnl:+.2f} $ ({trade.get('pnl_pct', 0):+.2f}%)",
                inline=True,
            )
            embed.add_field(
                name="Duration",
                value=f"{int(trade.get('duration_s', 0))}s",
                inline=True,
            )
            embed.add_field(
                name="Reason", value=trade.get("close_reason", "n/a"), inline=True
            )
            embed.add_field(name="📊 Portfolio", value=self._portfolio_summary(), inline=False)
            await self._target_channel.send(embed=embed)

    async def _handle_alert(self, data: dict) -> None:
        if not self._target_channel:
            return
        level = data.get("level", "info").upper()
        message = data.get("message", "")
        emoji = {
            "INFO": ":information_source:",
            "WARNING": ":warning:",
            "ERROR": ":rotating_light:",
            "CRITICAL": ":rotating_light:",
        }.get(level, ":bell:")
        await self._target_channel.send(f"{emoji} **[{level}]** {message}")


def main() -> None:
    if not DISCORD_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not set — exiting.")
        return
    client = GoldenDiscord()
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
