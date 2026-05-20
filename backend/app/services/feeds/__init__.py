"""Pluggable price-feed backends.

Public symbol: `price_feed` (instance) — the engine, API and Discord layers
import this and never touch the concrete backend directly.

Selection logic at import time:
- If OANDA key + accountID are set AND TwelveData key is set: FailoverPriceFeed(oanda, twelvedata)
- If only OANDA configured: OandaFeed (with internal REST fallback)
- If only TwelveData (or neither — mock mode): TwelveDataFeed
- An explicit FEED_PROVIDER env overrides the choice when both are configured.
"""

from __future__ import annotations

from loguru import logger

from app.config import settings
from app.services.feeds.base import BasePriceFeed
from app.services.feeds.failover import FailoverPriceFeed
from app.services.feeds.oanda import OandaFeed
from app.services.feeds.twelvedata import TwelveDataFeed


def _build_active() -> BasePriceFeed | FailoverPriceFeed:
    has_oanda = bool(settings.oanda_api_key and settings.oanda_account_id)
    has_td = bool(settings.twelvedata_api_key)

    pref = (settings.feed_provider or "auto").lower()

    if has_oanda and has_td and pref in ("auto", "oanda"):
        logger.info("Feeds: OANDA primary, TwelveData fallback (failover)")
        return FailoverPriceFeed(primary=OandaFeed(), secondary=TwelveDataFeed())
    if has_oanda and has_td and pref == "twelvedata":
        logger.info("Feeds: TwelveData primary, OANDA fallback (failover)")
        return FailoverPriceFeed(primary=TwelveDataFeed(), secondary=OandaFeed())
    if has_oanda and not has_td:
        logger.info("Feeds: OANDA only")
        return OandaFeed()
    if has_td or not has_oanda:
        # TwelveData includes a mock mode when no key is set, keeping dev possible offline
        logger.info("Feeds: TwelveData only")
        return TwelveDataFeed()
    logger.warning("No feed configured — TwelveData mock mode")
    return TwelveDataFeed()


price_feed = _build_active()

__all__ = [
    "BasePriceFeed",
    "FailoverPriceFeed",
    "OandaFeed",
    "TwelveDataFeed",
    "price_feed",
]
