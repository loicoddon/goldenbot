"""System prompts and prompt builders for pre-trade and post-trade analysis."""

from __future__ import annotations

from datetime import datetime
from typing import Any

PRE_TRADE_SYSTEM = (
    "You are a senior quantitative trading analyst specialized in XAU/USD (gold) "
    "intraday scalping. You evaluate a candidate trade BEFORE it is opened. "
    "Be cautious with high-impact macro events.\n\n"
    "Return STRICT JSON with this exact schema:\n"
    "{\n"
    '  "score": <float 0-100, your overall confidence the trade is good>,\n'
    '  "recommendation": "PROCEED" | "REJECT" | "REDUCE_SIZE",\n'
    '  "factors": [<list of 1-5 short strings explaining drivers>],\n'
    '  "warnings": [<list of risks, may be empty>],\n'
    '  "summary": "<one-sentence verdict>"\n'
    "}\n"
    "Output ONLY the JSON object, no markdown, no extra text."
)

POST_TRADE_SYSTEM = (
    "You are a senior quantitative trading analyst specialized in XAU/USD (gold) "
    "intraday scalping. You analyze a CLOSED trade to learn from it.\n\n"
    "Return STRICT JSON with this exact schema:\n"
    "{\n"
    '  "quality_score": <float 0-100, retrospective quality of the setup>,\n'
    '  "summary": "<2-3 sentence verdict>",\n'
    '  "factors": [<list of key drivers, gains or pitfalls>],\n'
    '  "improvements": "<actionable suggestion for similar setups>"\n'
    "}\n"
    "Output ONLY the JSON object, no markdown, no extra text."
)


def build_pre_trade_prompt(
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    price: float,
    stop_loss: float,
    take_profit: float,
    strategy_confidence: float,
    indicators: dict[str, Any],
    recent_news: list[dict[str, Any]],
    upcoming_events: list[dict[str, Any]],
) -> str:
    indicator_lines = "\n".join(
        f"  - {k}: {_format_value(v)}" for k, v in indicators.items()
    ) or "  (none)"
    news_lines = "\n".join(
        f"  - [{n.get('published_at', '?')}] {n.get('headline', '')}"
        for n in recent_news[:5]
    ) or "  (no recent gold-relevant headlines)"
    event_lines = "\n".join(
        f"  - {e.get('event_time', '?')} [{e.get('impact', '?').upper()}] "
        f"{e.get('country', '')} — {e.get('title', '')}"
        for e in upcoming_events[:5]
    ) or "  (no upcoming events in window)"
    return (
        f"Candidate trade — {symbol} ({timeframe})\n"
        f"Direction: {direction}\n"
        f"Entry price: {price:.2f}\n"
        f"Stop-loss: {stop_loss:.2f}\n"
        f"Take-profit: {take_profit:.2f}\n"
        f"Risk/Reward ratio: {_rr(price, stop_loss, take_profit, direction):.2f}\n"
        f"Strategy confidence (technical): {strategy_confidence:.1f}/100\n\n"
        f"Technical indicators:\n{indicator_lines}\n\n"
        f"Recent gold-relevant headlines:\n{news_lines}\n\n"
        f"Upcoming economic events (next ~24h):\n{event_lines}\n\n"
        f"Now: {datetime.utcnow().isoformat()}Z\n\n"
        "Evaluate this setup and return STRICT JSON."
    )


def build_post_trade_prompt(
    *,
    trade: Any,  # Trade ORM instance
    recent_news: list[dict[str, Any]],
    relevant_events: list[dict[str, Any]],
) -> str:
    duration = (
        (trade.closed_at - trade.opened_at).total_seconds()
        if trade.closed_at and trade.opened_at
        else 0
    )
    news_lines = "\n".join(
        f"  - [{n.get('published_at', '?')}] {n.get('headline', '')}"
        for n in recent_news[:5]
    ) or "  (none)"
    event_lines = "\n".join(
        f"  - {e.get('event_time', '?')} [{e.get('impact', '?').upper()}] {e.get('title', '')}"
        for e in relevant_events[:5]
    ) or "  (none)"
    return (
        f"Closed trade on {trade.symbol} ({trade.timeframe}).\n"
        f"Side: {trade.side.value}\n"
        f"Entry: {trade.entry_price:.2f}\n"
        f"Exit: {trade.exit_price:.2f}\n"
        f"Stop-loss: {trade.stop_loss:.2f}\n"
        f"Take-profit: {trade.take_profit:.2f}\n"
        f"Size: {trade.size:.4f}\n"
        f"Risk: {trade.risk_amount:.2f} USD\n"
        f"PnL: {trade.pnl:+.2f} USD ({trade.pnl_pct:+.2f}% of risk)\n"
        f"Close reason: {trade.close_reason.value if trade.close_reason else 'n/a'}\n"
        f"Strategy: {trade.strategy}\n"
        f"Initial reason: {trade.reason}\n"
        f"Pre-trade technical confidence: {trade.confidence_score}\n"
        f"Duration: {int(duration)}s\n"
        f"Opened: {trade.opened_at}\nClosed: {trade.closed_at}\n\n"
        f"News during trade lifetime:\n{news_lines}\n\n"
        f"Economic events during trade lifetime:\n{event_lines}\n\n"
        "Analyze and return STRICT JSON."
    )


def _format_value(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _rr(entry: float, sl: float, tp: float, direction: str) -> float:
    if direction == "BUY":
        risk = entry - sl
        reward = tp - entry
    else:
        risk = sl - entry
        reward = entry - tp
    if risk <= 0:
        return 0.0
    return reward / risk
