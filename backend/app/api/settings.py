from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bot_settings import BotSettings
from app.schemas.settings import BotSettingsOut, BotSettingsUpdate

router = APIRouter()


@router.get("", response_model=BotSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    bot = await db.scalar(select(BotSettings).where(BotSettings.id == 1))
    if not bot:
        raise HTTPException(status_code=404, detail="Settings not initialized")
    return bot


@router.patch("", response_model=BotSettingsOut)
async def update_settings(
    payload: BotSettingsUpdate, db: AsyncSession = Depends(get_db)
):
    bot = await db.scalar(select(BotSettings).where(BotSettings.id == 1))
    if not bot:
        raise HTTPException(status_code=404, detail="Settings not initialized")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(bot, key, value)
    await db.commit()
    await db.refresh(bot)
    return bot
