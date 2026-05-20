"""Backwards-compat shim.

The pluggable feeds live in `app.services.feeds`. This module re-exports the
active `price_feed` so old imports keep working.
"""

from app.services.feeds import price_feed  # noqa: F401

__all__ = ["price_feed"]
