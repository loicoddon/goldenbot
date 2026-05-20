"""Lightweight optimizer: adjusts thresholds based on rolling performance.

Phase 2 logic (deliberately conservative):
- Compute winrate + expectancy over last N closed trades.
- If winrate < 35% → bump min_confidence by +5 (cap 90).
- If winrate > 65% AND expectancy positive → drop min_confidence by -3 (floor 30).
- Identify best session (Asia/London/NY) — purely informational, logged + persisted in details.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_bus import CHANNEL_ALERT, bus
from app.models.bot_settings import BotSettings
from app.models.trade import Trade, TradeStatus


def _session_of(ts: datetime) -> str:
    h = ts.hour
    if 0 <= h < 7:
        return "asia"
    if 7 <= h < 13:
        return "london"
    if 13 <= h < 21:
        return "ny"
    return "asia"


class Optimizer:
    @staticmethod
    async def run(session: AsyncSession) -> dict[str, Any] | None:
        bot = await session.scalar(select(BotSettings).where(BotSettings.id == 1))
        if bot is None or not bot.optimizer_enabled:
            return None

        window = max(5, bot.optimizer_window_trades)
        rows = (
            await session.scalars(
                select(Trade)
                .where(Trade.status == TradeStatus.CLOSED)
                .order_by(desc(Trade.closed_at))
                .limit(window)
            )
        ).all()
        if len(rows) < 5:
            return None  # not enough signal yet

        wins = [t for t in rows if (t.pnl or 0) > 0]
        winrate = (len(wins) / len(rows)) * 100
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        losses = [t for t in rows if (t.pnl or 0) <= 0]
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0.0
        expectancy = (winrate / 100) * avg_win + (1 - winrate / 100) * avg_loss

        # Session breakdown
        by_session: dict[str, list[Trade]] = defaultdict(list)
        for t in rows:
            ts = t.closed_at or t.opened_at
            by_session[_session_of(ts)].append(t)
        session_perf = {}
        best_session = None
        best_score = float("-inf")
        for s, ts in by_session.items():
            if not ts:
                continue
            w = sum(1 for t in ts if (t.pnl or 0) > 0) / len(ts) * 100
            avg = sum(t.pnl or 0 for t in ts) / len(ts)
            score = avg * (w / 100)
            session_perf[s] = {"winrate": w, "avg_pnl": avg, "count": len(ts)}
            if score > best_score:
                best_score = score
                best_session = s

        old_min = bot.min_confidence
        change_reason = "stable"
        if winrate < 35:
            bot.min_confidence = min(90.0, old_min + 5.0)
            change_reason = "low_winrate"
        elif winrate > 65 and expectancy > 0:
            bot.min_confidence = max(30.0, old_min - 3.0)
            change_reason = "strong_performance"
        await session.commit()

        result = {
            "evaluated_at": datetime.utcnow().isoformat(),
            "window_size": len(rows),
            "winrate": winrate,
            "expectancy": expectancy,
            "old_min_confidence": old_min,
            "new_min_confidence": bot.min_confidence,
            "change_reason": change_reason,
            "best_session": best_session,
            "session_perf": session_perf,
        }
        logger.info(
            "Optimizer: winrate={:.1f}% exp={:+.2f} min_conf {} -> {} ({})",
            winrate,
            expectancy,
            old_min,
            bot.min_confidence,
            change_reason,
        )
        if change_reason != "stable":
            await bus.publish(
                CHANNEL_ALERT,
                {
                    "level": "info",
                    "message": (
                        f"Optimizer adjusted min_confidence {old_min:.1f} → "
                        f"{bot.min_confidence:.1f} ({change_reason}, "
                        f"winrate {winrate:.1f}% over {len(rows)} trades)"
                    ),
                },
            )
        return result


optimizer = Optimizer()
