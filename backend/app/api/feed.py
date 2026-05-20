from fastapi import APIRouter

from app.services.feeds import FailoverPriceFeed, price_feed

router = APIRouter()


@router.get("/status")
async def status():
    is_failover = isinstance(price_feed, FailoverPriceFeed)
    info: dict = {
        "type": "failover" if is_failover else "single",
        "active": price_feed.active_name if is_failover else price_feed.name,
        "last_price": price_feed.last_price,
        "last_tick_ts": (
            price_feed.last_timestamp.isoformat() if price_feed.last_timestamp else None
        ),
    }
    if is_failover:
        info["primary"] = price_feed._primary.name  # type: ignore[attr-defined]
        info["secondary"] = price_feed._secondary.name  # type: ignore[attr-defined]
    return info


@router.post("/restart")
async def restart():
    if isinstance(price_feed, FailoverPriceFeed):
        await price_feed.restart()
    else:
        await price_feed.stop()
        await price_feed.start()
    return {"ok": True, "active": getattr(price_feed, "active_name", price_feed.name)}
