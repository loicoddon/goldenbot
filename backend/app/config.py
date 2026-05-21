from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://goldenbot:changeme_local_only@db:5432/goldenbot"
    )

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # Market data — feed selection
    feed_provider: str = Field(default="auto")  # auto | oanda | twelvedata

    # TwelveData
    twelvedata_api_key: str = Field(default="")
    twelvedata_symbol: str = Field(default="XAU/USD")
    twelvedata_poll_interval: float = Field(default=2.0)

    # OANDA
    oanda_api_key: str = Field(default="")
    oanda_account_id: str = Field(default="")
    oanda_env: str = Field(default="practice")  # practice | live

    # Correlated markets feed (DXY, TNX, WTI, SPX via TwelveData)
    # Disabled by default — these symbols require paid TwelveData plan
    correlated_feed_enabled: bool = Field(default=False)

    # News (Finnhub)
    finnhub_api_key: str = Field(default="")
    news_calendar_poll_interval: int = Field(default=300)
    news_headlines_poll_interval: int = Field(default=120)
    news_block_before_min: int = Field(default=15)
    news_block_after_min: int = Field(default=15)

    # Discord
    discord_bot_token: str = Field(default="")
    discord_channel_id: str = Field(default="")

    # AI
    ai_provider: Literal["claude", "ollama", "stub"] = Field(default="stub")
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-opus-4-7")
    ollama_base_url: str = Field(default="http://host.docker.internal:11434")
    ollama_model: str = Field(default="qwen2.5:14b")

    # Trading
    initial_capital: float = Field(default=1000.0)
    risk_per_trade_pct: float = Field(default=1.0)
    daily_loss_limit_pct: float = Field(default=5.0)
    max_trades_per_day: int = Field(default=10)
    default_timeframe: str = Field(default="1m")
    leverage: int = Field(default=500)

    # Optimizer
    optimizer_enabled: bool = Field(default=True)
    optimizer_window_trades: int = Field(default=20)
    optimizer_run_every_trades: int = Field(default=10)

    # Logging
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
