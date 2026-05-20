"""Trading session helper (UTC-based)."""

from __future__ import annotations

from datetime import datetime, timezone


def current_session(now: datetime | None = None) -> str:
    """Return one of: asia | london | ny."""
    now = now or datetime.now(timezone.utc)
    h = now.hour
    if 0 <= h < 7:
        return "asia"
    if 7 <= h < 13:
        return "london"
    if 13 <= h < 21:
        return "ny"
    return "asia"


def session_min_confidence(
    base: float,
    overrides: dict[str, float] | None,
    session: str | None = None,
) -> float:
    """Apply per-session min_confidence override if any."""
    overrides = overrides or {}
    s = session or current_session()
    if s in overrides:
        return float(overrides[s])
    return base
