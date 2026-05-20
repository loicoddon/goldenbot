"""Multi-IA voting: 4 specialized agents that vote on a candidate trade.

Agents:
- TechnicalAgent: focuses on indicators, structure, momentum
- NewsAgent: focuses on macro news + economic calendar
- RiskAgent: focuses on R/R, position vs limits, volatility regime
- DecisionalAgent: synthesizes the three above into a final verdict

Each agent returns {score: 0-100, recommendation: PROCEED|REJECT|REDUCE_SIZE, summary, factors}.
The coordinator applies configurable weights, returns a fused PreTradeResult.

Underlying LLM provider is selected per agent (default = bot.ai_provider).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.ai.analyzer import (
    ClaudeAnalyzer,
    OllamaAnalyzer,
    PreTradeResult,
    _gather_context,
)

AGENT_DEFAULT_WEIGHTS = {
    "technical": 0.30,
    "news": 0.20,
    "risk": 0.20,
    "decisional": 0.30,
}


@dataclass
class AgentVote:
    agent: str
    score: float
    recommendation: str
    summary: str
    factors: list[str]


TECHNICAL_PROMPT = (
    "You are the TECHNICAL specialist in a 4-member trading committee for XAU/USD scalping.\n"
    "Focus ONLY on: trend, momentum, volatility, support/resistance, RSI/EMA/ATR.\n"
    "Ignore news. Return JSON: "
    '{"score":0-100,"recommendation":"PROCEED|REJECT|REDUCE_SIZE","summary":"...","factors":[...]}'
)

NEWS_PROMPT = (
    "You are the NEWS/MACRO specialist. Evaluate impact of recent headlines and upcoming "
    "economic events on this XAU/USD trade. Gold tends to fall with strong USD/yields, "
    "rise with risk-off / dovish FED / war. Ignore pure technicals.\n"
    "Return JSON: "
    '{"score":0-100,"recommendation":"PROCEED|REJECT|REDUCE_SIZE","summary":"...","factors":[...]}'
)

RISK_PROMPT = (
    "You are the RISK manager. Evaluate the trade's R/R, SL distance vs ATR, leverage "
    "exposure, and time-of-day context. Reject if R/R below 1.2 or SL within typical noise.\n"
    "Return JSON: "
    '{"score":0-100,"recommendation":"PROCEED|REJECT|REDUCE_SIZE","summary":"...","factors":[...]}'
)

DECISIONAL_PROMPT = (
    "You are the DECISIONAL synthesizer. Below are the votes of TECHNICAL, NEWS, and RISK "
    "agents. Produce a final verdict. Weight conflicting signals; if 2+ agents disagree with "
    "PROCEED, lean toward REJECT.\n"
    "Return JSON: "
    '{"score":0-100,"recommendation":"PROCEED|REJECT|REDUCE_SIZE","summary":"...","factors":[...]}'
)


def _build_user_prompt(
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    price: float,
    sl: float,
    tp: float,
    strategy_confidence: float,
    indicators: dict[str, Any],
    news: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    correlated: dict[str, Any] | None = None,
) -> str:
    indicator_block = "\n".join(f"  {k}: {v}" for k, v in (indicators or {}).items()) or "  (none)"
    news_block = "\n".join(
        f"  - [{n.get('published_at')}] {n.get('headline')}" for n in (news or [])[:5]
    ) or "  (none)"
    event_block = "\n".join(
        f"  - {e.get('event_time')} [{e.get('impact', '?').upper()}] {e.get('country', '')} {e.get('title')}"
        for e in (events or [])[:5]
    ) or "  (none)"
    corr_block = (
        "\n".join(f"  {k}: {v}" for k, v in (correlated or {}).items()) or "  (none)"
    )
    rr = _rr(price, sl, tp, direction)
    return (
        f"Candidate trade: {direction} {symbol} @ {price:.2f} "
        f"SL={sl:.2f} TP={tp:.2f} R/R={rr:.2f} timeframe={timeframe}\n"
        f"Technical strategy confidence: {strategy_confidence:.1f}/100\n\n"
        f"Indicators:\n{indicator_block}\n\n"
        f"Recent gold-relevant headlines:\n{news_block}\n\n"
        f"Upcoming economic events:\n{event_block}\n\n"
        f"Correlated markets snapshot:\n{corr_block}\n\n"
        "Return STRICT JSON only."
    )


def _rr(price: float, sl: float, tp: float, direction: str) -> float:
    if direction == "BUY":
        risk = price - sl
        reward = tp - price
    else:
        risk = sl - price
        reward = price - tp
    if risk <= 0:
        return 0.0
    return reward / risk


async def _call_llm(provider: str, system: str, user: str, max_seconds: int = 45) -> dict | None:
    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=max_seconds) as c:
                r = await c.post(
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
                r.raise_for_status()
                content = (r.json().get("message") or {}).get("content", "")
                return _safe_json(content)
        except Exception as e:
            logger.warning("Ollama agent call failed: {}", e)
            return None
    if provider == "claude":
        client = await ClaudeAnalyzer._client()
        if client is None:
            return None
        try:
            r = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=600,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(b.text for b in r.content if hasattr(b, "text"))
            return _safe_json(text)
        except Exception as e:
            logger.warning("Claude agent call failed: {}", e)
            return None
    return None


def _safe_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _parse_vote(agent: str, data: dict | None, strategy_confidence: float) -> AgentVote:
    if not data:
        return AgentVote(
            agent=agent,
            score=strategy_confidence,
            recommendation="PROCEED" if strategy_confidence >= 50 else "REJECT",
            summary=f"{agent}: no LLM response — pass-through",
            factors=[],
        )
    return AgentVote(
        agent=agent,
        score=float(data.get("score", strategy_confidence)),
        recommendation=str(data.get("recommendation", "PROCEED")).upper(),
        summary=str(data.get("summary", ""))[:300],
        factors=list(data.get("factors", []) or []),
    )


async def vote(
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
    correlated: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
    provider: str | None = None,
) -> tuple[PreTradeResult, list[AgentVote]]:
    """Run TECHNICAL/NEWS/RISK in parallel, then DECISIONAL, fuse votes."""
    weights = weights or AGENT_DEFAULT_WEIGHTS
    provider = (provider or settings.ai_provider or "stub").lower()

    # Context gathering (shared across agents)
    news, events = await _gather_context(session)

    user_prompt = _build_user_prompt(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        price=price,
        sl=stop_loss,
        tp=take_profit,
        strategy_confidence=strategy_confidence,
        indicators=indicators,
        news=news,
        events=events,
        correlated=correlated,
    )

    if provider == "stub":
        # Deterministic fallback — no LLM calls
        pretrade = PreTradeResult(
            score=strategy_confidence,
            recommendation="PROCEED" if strategy_confidence >= 50 else "REJECT",
            summary="Multi-IA stub: passing through strategy confidence.",
        )
        return pretrade, []

    # If primary is Ollama and it has degraded, escalate to Claude transparently
    if provider == "ollama" and OllamaAnalyzer._should_fallback():
        logger.info("Multi-IA: Ollama threshold reached, using Claude for this round")
        provider = "claude"

    tech, news_vote, risk_vote = await asyncio.gather(
        _call_llm(provider, TECHNICAL_PROMPT, user_prompt),
        _call_llm(provider, NEWS_PROMPT, user_prompt),
        _call_llm(provider, RISK_PROMPT, user_prompt),
        return_exceptions=False,
    )

    # Track Ollama health if applicable
    if provider == "ollama":
        if any(v is None for v in (tech, news_vote, risk_vote)):
            OllamaAnalyzer._record_failure()
        else:
            OllamaAnalyzer._record_success()

    votes = [
        _parse_vote("technical", tech, strategy_confidence),
        _parse_vote("news", news_vote, strategy_confidence),
        _parse_vote("risk", risk_vote, strategy_confidence),
    ]

    # Decisional synthesizer
    decisional_user = (
        user_prompt
        + "\n\nTeam votes so far:\n"
        + "\n".join(
            f"- {v.agent}: score={v.score:.0f}, rec={v.recommendation}, {v.summary}"
            for v in votes
        )
        + "\n\nNow produce the FINAL verdict as STRICT JSON."
    )
    dec_raw = await _call_llm(provider, DECISIONAL_PROMPT, decisional_user, max_seconds=45)
    if provider == "ollama":
        if dec_raw is None:
            OllamaAnalyzer._record_failure()
        else:
            OllamaAnalyzer._record_success()
    dec_vote = _parse_vote("decisional", dec_raw, strategy_confidence)
    votes.append(dec_vote)

    # Weighted score
    total_weight = sum(weights.get(v.agent, 0.0) for v in votes) or 1.0
    weighted_score = (
        sum(v.score * weights.get(v.agent, 0.0) for v in votes) / total_weight
    )

    # Final recommendation: respect decisional unless 2+ others REJECT
    rejects = sum(1 for v in votes[:3] if v.recommendation == "REJECT")
    if rejects >= 2:
        final_rec = "REJECT"
    elif dec_vote.recommendation == "REJECT":
        final_rec = "REJECT"
    elif dec_vote.recommendation == "REDUCE_SIZE":
        final_rec = "REDUCE_SIZE"
    else:
        final_rec = "PROCEED"

    summary = "; ".join(f"{v.agent}:{v.recommendation}" for v in votes)
    pretrade = PreTradeResult(
        score=weighted_score,
        recommendation=final_rec,
        factors=[f for v in votes for f in v.factors][:8],
        warnings=[v.summary for v in votes if v.recommendation == "REJECT"],
        summary=summary,
        raw={"votes": [v.__dict__ for v in votes], "weights": weights},
    )
    return pretrade, votes
