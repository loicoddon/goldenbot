from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import bot as bot_router
from app.api import portfolio as portfolio_router
from app.api import prices as prices_router
from app.api import settings as settings_router
from app.api import trades as trades_router
from app.api import ws as ws_router
from app.api import backtest as backtest_router
from app.api import feed as feed_router
from app.api import news as news_router
from app.core.logger import setup_logger
from app.core.redis_bus import bus
from app.database import init_db
from app.services.correlated_feed import correlated_feed
from app.services.engine_runner import engine_runner
from app.services.news_feed import news_feed
from app.services.price_feed import price_feed

setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GoldenBot backend…")
    await init_db()
    await bus.connect()
    await engine_runner.bootstrap()
    yield
    logger.info("Shutting down GoldenBot backend…")
    await engine_runner.stop()
    await news_feed.stop()
    await correlated_feed.stop()
    await price_feed.stop()
    await bus.close()


app = FastAPI(
    title="GoldenBot API",
    description="Virtual XAU/USD trading bot — backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"name": "GoldenBot", "version": "0.1.0", "status": "ok"}


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "engine": engine_runner.status()}


app.include_router(trades_router.router, prefix="/api/trades", tags=["trades"])
app.include_router(portfolio_router.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(prices_router.router, prefix="/api/prices", tags=["prices"])
app.include_router(bot_router.router, prefix="/api/bot", tags=["bot"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(news_router.router, prefix="/api/news", tags=["news"])
app.include_router(backtest_router.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(feed_router.router, prefix="/api/feed", tags=["feed"])
app.include_router(ws_router.router, tags=["ws"])
