"""Pluggable AI analyzer interface — pre-trade + post-trade.

Phase 2 implementations:
- StubAnalyzer (offline, deterministic)
- ClaudeAnalyzer (Anthropic API)
- OllamaAnalyzer (local LLM via Ollama, format=json)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.news import EconomicEvent, NewsItem
from app.models.trade import Trade, TradeAnalysis
from app.services.ai.prompts import (
    POST_TRADE_SYSTEM,
    PRE_TRADE_SYSTEM,
    build_post_trade_prompt,
    build_pre_trade_prompt,
)


@dataclass
class PreTradeResult:
    score: float
    recommendation: str  # PROCEED | REJECT | REDUCE_SIZE
    factors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BaseAnalyzer(ABC):
    name: str = "base"

    @abstractmethod
    async def analyze_post_trade(
        self, session: AsyncSession, trade: Trade
    ) -> TradeAnalysis: ...

    @abstractmethod
    async def analyze_pre_trade(
        self,
        session: AsyncSession,
        *,
        symbol: str,
        timeframe: str,
        direction: str,
        price: float,
        stop_loss: float,
        take_profit: float,
        strategy_confidence: float,
        indicators: dict[str, Any],
    ) -> PreTradeResult: ...


async def _gather_context(
    session: AsyncSession, *, lookback_hours: int = 24, future_hours: int = 24
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.now(timezone.utc)
    headlines = (
        await session.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= now - timedelta(hours=lookback_hours))
            .order_by(desc(NewsItem.published_at))
            .limit(8)
        )
    ).all()
    events = (
        await session.scalars(
            select(EconomicEvent)
            .where(EconomicEvent.event_time >= now - timedelta(hours=1))
            .where(EconomicEvent.event_time <= now + timedelta(hours=future_hours))
            .order_by(EconomicEvent.event_time)
            .limit(10)
        )
    ).all()
    news_dicts = [
        {
            "headline": n.headline,
            "summary": n.summary,
            "published_at": n.published_at.isoformat() if n.published_at else None,
            "relevance": n.relevance,
        }
        for n in headlines
    ]
    event_dicts = [
        {
            "title": e.title,
            "impact": e.impact,
            "country": e.country,
            "event_time": e.event_time.isoformat() if e.event_time else None,
            "actual": e.actual,
            "estimate": e.estimate,
            "previous": e.previous,
        }
        for e in events
    ]
    return news_dicts, event_dicts


async def _gather_post_trade_context(
    session: AsyncSession, trade: Trade
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    start = trade.opened_at
    end = trade.closed_at or datetime.utcnow()
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    # Pad ±30 minutes
    start_p = start - timedelta(minutes=30)
    end_p = end + timedelta(minutes=30)
    headlines = (
        await session.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= start_p)
            .where(NewsItem.published_at <= end_p)
            .order_by(NewsItem.published_at)
            .limit(8)
        )
    ).all()
    events = (
        await session.scalars(
            select(EconomicEvent)
            .where(EconomicEvent.event_time >= start_p)
            .where(EconomicEvent.event_time <= end_p)
            .order_by(EconomicEvent.event_time)
            .limit(10)
        )
    ).all()
    return (
        [
            {
                "headline": n.headline,
                "published_at": n.published_at.isoformat() if n.published_at else None,
            }
            for n in headlines
        ],
        [
            {
                "title": e.title,
                "impact": e.impact,
                "event_time": e.event_time.isoformat() if e.event_time else None,
            }
            for e in events
        ],
    )


class StubAnalyzer(BaseAnalyzer):
    name = "stub"

    async def analyze_post_trade(self, session, trade) -> TradeAnalysis:
        won = (trade.pnl or 0) > 0
        summary = (
            f"Trade {'WIN' if won else 'LOSS'}: {trade.side.value} {trade.symbol} "
            f"entry={trade.entry_price:.2f} exit={trade.exit_price:.2f} "
            f"pnl={trade.pnl:+.2f}$ via {trade.close_reason.value if trade.close_reason else 'n/a'}."
        )
        analysis = TradeAnalysis(
            trade_id=trade.id,
            phase="post",
            provider=self.name,
            quality_score=70.0 if won else 40.0,
            confidence_score=trade.confidence_score,
            summary=summary,
            improvements="Enable a real AI provider (claude/ollama) for actionable insight.",
            details={"stub": True},
        )
        session.add(analysis)
        await session.commit()
        return analysis

    async def analyze_pre_trade(
        self,
        session,
        *,
        symbol,
        timeframe,
        direction,
        price,
        stop_loss,
        take_profit,
        strategy_confidence,
        indicators,
    ) -> PreTradeResult:
        return PreTradeResult(
            score=strategy_confidence,
            recommendation="PROCEED" if strategy_confidence >= 50 else "REJECT",
            summary="Stub analyzer — passes through strategy confidence.",
        )


class ClaudeAnalyzer(BaseAnalyzer):
    name = "claude"

    async def analyze_pre_trade(
        self,
        session,
        *,
        symbol,
        timeframe,
        direction,
        price,
        stop_loss,
        take_profit,
        strategy_confidence,
        indicators,
    ) -> PreTradeResult:
        client = await self._client()
        if client is None:
            return await StubAnalyzer().analyze_pre_trade(
                session,
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_confidence=strategy_confidence,
                indicators=indicators,
            )
        news, events = await _gather_context(session)
        prompt = build_pre_trade_prompt(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_confidence=strategy_confidence,
            indicators=indicators,
            recent_news=news,
            upcoming_events=events,
        )
        try:
            resp = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=800,
                system=PRE_TRADE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            data = _safe_json(text)
        except Exception as e:
            logger.warning("Claude pre-trade failed: {}", e)
            return await StubAnalyzer().analyze_pre_trade(
                session,
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_confidence=strategy_confidence,
                indicators=indicators,
            )
        return PreTradeResult(
            score=float(data.get("score", strategy_confidence)),
            recommendation=str(data.get("recommendation", "PROCEED")).upper(),
            factors=list(data.get("factors", []) or []),
            warnings=list(data.get("warnings", []) or []),
            summary=str(data.get("summary", ""))[:500],
            raw=data,
        )

    async def analyze_post_trade(self, session, trade) -> TradeAnalysis:
        client = await self._client()
        if client is None:
            return await StubAnalyzer().analyze_post_trade(session, trade)
        news, events = await _gather_post_trade_context(session, trade)
        prompt = build_post_trade_prompt(
            trade=trade, recent_news=news, relevant_events=events
        )
        try:
            resp = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=POST_TRADE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            data = _safe_json(text)
        except Exception as e:
            logger.warning("Claude post-trade failed: {}", e)
            return await StubAnalyzer().analyze_post_trade(session, trade)

        analysis = TradeAnalysis(
            trade_id=trade.id,
            phase="post",
            provider=self.name,
            quality_score=float(data.get("quality_score", 50)),
            confidence_score=trade.confidence_score,
            summary=str(data.get("summary", ""))[:2000],
            improvements=str(data.get("improvements", ""))[:2000],
            details=data,
        )
        session.add(analysis)
        await session.commit()
        return analysis

    @staticmethod
    async def _client():
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            logger.warning("anthropic SDK not installed; falling back to stub")
            return None
        if not settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY missing; falling back to stub")
            return None
        return AsyncAnthropic(api_key=settings.anthropic_api_key)


class OllamaAnalyzer(BaseAnalyzer):
    """Ollama analyzer with automatic Claude fallback.

    Tracks consecutive failures (None response from /api/chat or empty JSON).
    When `_failure_threshold` consecutive failures are reached AND a Claude
    key is configured, subsequent calls are delegated to ClaudeAnalyzer until
    Ollama returns a valid response again, at which point the counter resets.
    """

    name = "ollama"
    _consecutive_failures: int = 0
    _failure_threshold: int = 3

    @classmethod
    def _record_failure(cls) -> None:
        cls._consecutive_failures += 1
        logger.warning(
            "Ollama failure #{} (threshold for Claude fallback: {})",
            cls._consecutive_failures,
            cls._failure_threshold,
        )

    @classmethod
    def _record_success(cls) -> None:
        if cls._consecutive_failures > 0:
            logger.info("Ollama recovered — reset failure counter")
        cls._consecutive_failures = 0

    @classmethod
    def _should_fallback(cls) -> bool:
        return (
            cls._consecutive_failures >= cls._failure_threshold
            and bool(settings.anthropic_api_key)
        )

    async def analyze_pre_trade(
        self,
        session,
        *,
        symbol,
        timeframe,
        direction,
        price,
        stop_loss,
        take_profit,
        strategy_confidence,
        indicators,
    ) -> PreTradeResult:
        if self._should_fallback():
            logger.info("Ollama has failed >= {}x — delegating pre-trade to Claude",
                        self._failure_threshold)
            return await ClaudeAnalyzer().analyze_pre_trade(
                session,
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_confidence=strategy_confidence,
                indicators=indicators,
            )

        news, events = await _gather_context(session)
        user_prompt = build_pre_trade_prompt(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_confidence=strategy_confidence,
            indicators=indicators,
            recent_news=news,
            upcoming_events=events,
        )
        data = await self._chat_json(PRE_TRADE_SYSTEM, user_prompt, max_seconds=45)
        if not data:
            self._record_failure()
            if self._should_fallback():
                logger.info("Threshold reached — falling back to Claude for this pre-trade call")
                return await ClaudeAnalyzer().analyze_pre_trade(
                    session,
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=direction,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy_confidence=strategy_confidence,
                    indicators=indicators,
                )
            return PreTradeResult(
                score=strategy_confidence,
                recommendation="PROCEED" if strategy_confidence >= 50 else "REJECT",
                summary="Ollama unavailable — passing through strategy confidence.",
            )
        self._record_success()
        return PreTradeResult(
            score=float(data.get("score", strategy_confidence)),
            recommendation=str(data.get("recommendation", "PROCEED")).upper(),
            factors=list(data.get("factors", []) or []),
            warnings=list(data.get("warnings", []) or []),
            summary=str(data.get("summary", ""))[:500],
            raw=data,
        )

    async def analyze_post_trade(self, session, trade) -> TradeAnalysis:
        if self._should_fallback():
            logger.info("Ollama has failed >= {}x — delegating post-trade to Claude",
                        self._failure_threshold)
            return await ClaudeAnalyzer().analyze_post_trade(session, trade)

        news, events = await _gather_post_trade_context(session, trade)
        prompt = build_post_trade_prompt(
            trade=trade, recent_news=news, relevant_events=events
        )
        data = await self._chat_json(POST_TRADE_SYSTEM, prompt, max_seconds=60)
        if not data:
            self._record_failure()
            if self._should_fallback():
                logger.info("Threshold reached — falling back to Claude for this post-trade call")
                return await ClaudeAnalyzer().analyze_post_trade(session, trade)
            return await StubAnalyzer().analyze_post_trade(session, trade)
        self._record_success()
        analysis = TradeAnalysis(
            trade_id=trade.id,
            phase="post",
            provider=self.name,
            quality_score=float(data.get("quality_score", 50)),
            confidence_score=trade.confidence_score,
            summary=str(data.get("summary", ""))[:2000],
            improvements=str(data.get("improvements", ""))[:2000],
            details=data,
        )
        session.add(analysis)
        await session.commit()
        return analysis

    @staticmethod
    async def _chat_json(system: str, user: str, max_seconds: int = 60) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=max_seconds) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.2},
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                content = (payload.get("message") or {}).get("content") or ""
                return _safe_json(content)
        except Exception as e:
            logger.warning("Ollama call failed: {}", e)
            return None


def _safe_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {}


_REGISTRY: dict[str, type[BaseAnalyzer]] = {
    "stub": StubAnalyzer,
    "claude": ClaudeAnalyzer,
    "ollama": OllamaAnalyzer,
}


def get_analyzer(name: str | None = None) -> BaseAnalyzer:
    key = (name or settings.ai_provider or "stub").lower()
    cls = _REGISTRY.get(key, StubAnalyzer)
    return cls()
