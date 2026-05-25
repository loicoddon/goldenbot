from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from sqlalchemy import text

    from app.models import (  # noqa: F401
        backtest,
        bot_settings,
        news,
        portfolio,
        price,
        signal,
        trade,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Hot migrations — idempotent ALTERs for columns added after initial schema.
        # Postgres "ADD COLUMN IF NOT EXISTS" makes this safe to re-run.
        migrations = [
            "ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS min_lot_size FLOAT DEFAULT 0",
            "ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS max_lot_size FLOAT DEFAULT 0",
            "ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS confidence_for_max_lot FLOAT DEFAULT 60",
        ]
        for sql in migrations:
            await conn.execute(text(sql))
