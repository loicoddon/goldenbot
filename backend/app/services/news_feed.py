"""Finnhub news + economic calendar feed.

Two polling loops:
- Economic calendar (every NEWS_CALENDAR_POLL_INTERVAL seconds)
- General news headlines filtered for gold/forex (every NEWS_HEADLINES_POLL_INTERVAL)

Both persist to DB and publish on the goldenbot:news Redis channel.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.core.redis_bus import CHANNEL_NEWS, bus
from app.database import SessionLocal
from app.models.news import EconomicEvent, NewsItem

CALENDAR_URL = "https://finnhub.io/api/v1/calendar/economic"
NEWS_URL = "https://finnhub.io/api/v1/news"

# Keywords that make a generic news item relevant to XAU/USD
GOLD_KEYWORDS = {
    "gold",
    "xau",
    "bullion",
    "precious metal",
    "fed",
    "fomc",
    "treasury",
    "yield",
    "inflation",
    "cpi",
    "ppi",
    "nfp",
    "dollar",
    "dxy",
    "rate hike",
    "rate cut",
    "powell",
    "geopolitic",
    "war",
    "sanction",
}

HIGH_IMPACT_KEYWORDS = {
    "cpi",
    "ppi",
    "nfp",
    "non-farm",
    "nonfarm",
    "fomc",
    "interest rate",
    "fed funds",
    "gdp",
    "unemployment rate",
    "retail sales",
    "core pce",
}

# Only events from these countries/regions actually move XAU/USD.
# Macau / Rwanda / Singapore PPIs etc. should never blanket-block trades.
HIGH_IMPACT_COUNTRIES = {
    "US",          # Fed, Treasury, NFP, CPI — primary driver
    "EU", "EUR",   # ECB
    "DE", "FR",    # Largest EU economies
    "GB", "UK",    # BoE
    "CN",          # PBoC, Chinese GDP — gold demand giant
    "JP",          # BoJ — global yen/yield impact
    "CH",          # SNB — safe-haven correlation
    "WW", "G7",    # Aggregate / multilateral
}


class NewsFeed:
    def __init__(self) -> None:
        self._calendar_task: asyncio.Task | None = None
        self._headlines_task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not settings.finnhub_api_key:
            logger.warning("FINNHUB_API_KEY missing — news feed disabled.")
            return
        self._stopping.clear()
        if self._calendar_task is None or self._calendar_task.done():
            self._calendar_task = asyncio.create_task(
                self._calendar_loop(), name="news_calendar"
            )
        if self._headlines_task is None or self._headlines_task.done():
            self._headlines_task = asyncio.create_task(
                self._headlines_loop(), name="news_headlines"
            )
        logger.info("NewsFeed started (Finnhub)")

    async def stop(self) -> None:
        self._stopping.set()
        for t in (self._calendar_task, self._headlines_task):
            if t:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        logger.info("NewsFeed stopped")

    async def _calendar_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._fetch_calendar()
            except Exception as e:
                logger.warning("Calendar fetch error: {}", e)
            await asyncio.sleep(settings.news_calendar_poll_interval)

    async def _headlines_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._fetch_headlines()
            except Exception as e:
                logger.warning("Headlines fetch error: {}", e)
            await asyncio.sleep(settings.news_headlines_poll_interval)

    async def _fetch_calendar(self) -> None:
        now = datetime.now(timezone.utc)
        params = {
            "token": settings.finnhub_api_key,
            "from": now.strftime("%Y-%m-%d"),
            "to": (now + timedelta(days=3)).strftime("%Y-%m-%d"),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(CALENDAR_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
        # Finnhub returns either:
        #   {"economicCalendar": [<events>]}                (newer free tier shape)
        #   {"economicCalendar": {"event": [<events>]}}     (older shape)
        raw = payload.get("economicCalendar")
        if isinstance(raw, list):
            events = raw
        elif isinstance(raw, dict):
            events = raw.get("event") or []
        else:
            events = []
        if not events:
            return
        upserted = 0
        async with SessionLocal() as session:
            for ev in events:
                row = self._normalize_event(ev)
                if row is None:
                    continue
                stmt = (
                    pg_insert(EconomicEvent)
                    .values(**row)
                    .on_conflict_do_update(
                        index_elements=["event_key"],
                        set_={
                            "actual": row.get("actual"),
                            "estimate": row.get("estimate"),
                            "previous": row.get("previous"),
                            "impact": row["impact"],
                        },
                    )
                )
                await session.execute(stmt)
                upserted += 1
            await session.commit()
        logger.info("Calendar: upserted {} events", upserted)
        await bus.publish(CHANNEL_NEWS, {"type": "calendar", "count": upserted})

    @staticmethod
    def _normalize_event(ev: dict[str, Any]) -> dict[str, Any] | None:
        title = (ev.get("event") or "").strip()
        country = (ev.get("country") or "").strip()
        time_s = ev.get("time")
        if not title or not time_s:
            return None
        try:
            event_time = datetime.fromisoformat(time_s.replace("Z", "+00:00"))
        except ValueError:
            try:
                event_time = datetime.strptime(time_s, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return None

        impact_score = ev.get("impact")
        title_lower = title.lower()
        country_up = country.upper() if country else ""
        # High impact requires BOTH a major-event keyword AND a country that
        # actually moves XAU/USD. Without this, Macau retail sales / Rwanda
        # rate decisions get blanket-classified high and block real trades.
        is_keyword = any(k in title_lower for k in HIGH_IMPACT_KEYWORDS)
        is_relevant_country = country_up in HIGH_IMPACT_COUNTRIES
        if is_keyword and is_relevant_country:
            impact = "high"
        elif impact_score in (3, "3", "high", "High") and is_relevant_country:
            impact = "high"
        elif (is_keyword or impact_score in (3, "3", "high", "High")):
            # Right kind of event but irrelevant country — downgrade
            impact = "medium"
        elif impact_score in (2, "2", "medium", "Medium"):
            impact = "medium"
        else:
            impact = "low"

        event_key = f"{country}|{title}|{event_time.isoformat()}"
        return {
            "event_key": event_key,
            "country": country or "US",
            "title": title,
            "impact": impact,
            "actual": _coerce_float(ev.get("actual")),
            "estimate": _coerce_float(ev.get("estimate")),
            "previous": _coerce_float(ev.get("prev")),
            "unit": ev.get("unit"),
            "event_time": event_time,
        }

    async def _fetch_headlines(self) -> None:
        params = {"token": settings.finnhub_api_key, "category": "general"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(NEWS_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
        if not isinstance(payload, list):
            return
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        inserted = 0
        async with SessionLocal() as session:
            for item in payload:
                normalized = self._normalize_news(item)
                if normalized is None or normalized["published_at"] < cutoff:
                    continue
                stmt = (
                    pg_insert(NewsItem)
                    .values(**normalized)
                    .on_conflict_do_nothing(index_elements=["external_id"])
                )
                result = await session.execute(stmt)
                if result.rowcount:
                    inserted += 1
            await session.commit()
        if inserted:
            logger.info("Headlines: inserted {} relevant items", inserted)
            await bus.publish(CHANNEL_NEWS, {"type": "headlines", "count": inserted})

    @staticmethod
    def _normalize_news(item: dict[str, Any]) -> dict[str, Any] | None:
        headline = (item.get("headline") or "").strip()
        if not headline:
            return None
        text = (headline + " " + (item.get("summary") or "")).lower()
        if not any(k in text for k in GOLD_KEYWORDS):
            return None
        ts = item.get("datetime")
        if not ts:
            return None
        published = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        relevance = sum(1 for k in GOLD_KEYWORDS if k in text) / 10.0
        return {
            "external_id": str(item.get("id") or f"{ts}:{headline[:60]}"),
            "source": item.get("source") or "finnhub",
            "category": item.get("category"),
            "headline": headline[:500],
            "summary": (item.get("summary") or "")[:2000] or None,
            "url": item.get("url"),
            "image_url": item.get("image"),
            "relevance": min(1.0, relevance),
            "published_at": published,
            "extra": None,
        }


def _coerce_float(v: Any) -> float | None:
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


news_feed = NewsFeed()


async def get_active_news_window(
    session, now: datetime | None = None
) -> EconomicEvent | None:
    """Return a high-impact event currently within the block window, if any."""
    now = now or datetime.now(timezone.utc)
    before = now + timedelta(minutes=settings.news_block_before_min)
    after = now - timedelta(minutes=settings.news_block_after_min)
    stmt = (
        select(EconomicEvent)
        .where(EconomicEvent.impact == "high")
        .where(EconomicEvent.event_time >= after)
        .where(EconomicEvent.event_time <= before)
        .order_by(EconomicEvent.event_time)
        .limit(1)
    )
    return await session.scalar(stmt)
