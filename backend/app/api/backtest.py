import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.backtest import BacktestRun, BacktestStatus
from app.schemas.backtest import BacktestCreate, BacktestDetailOut, BacktestOut
from app.services.backtest import run_backtest
from app.services.strategies import available_strategies

router = APIRouter()


@router.get("/strategies", response_model=list[str])
async def list_strategies():
    return available_strategies()


@router.post("/run", response_model=BacktestOut)
async def create_run(payload: BacktestCreate, db: AsyncSession = Depends(get_db)):
    if payload.from_ts >= payload.to_ts:
        raise HTTPException(status_code=400, detail="from_ts must be < to_ts")
    run = BacktestRun(
        symbol=payload.symbol,
        strategy=payload.strategy,
        timeframe=payload.timeframe,
        initial_capital=payload.initial_capital,
        leverage=payload.leverage,
        risk_per_trade_pct=payload.risk_per_trade_pct,
        params=payload.params,
        from_ts=payload.from_ts,
        to_ts=payload.to_ts,
        status=BacktestStatus.PENDING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    asyncio.create_task(run_backtest(run.id))
    return run


@router.get("", response_model=list[BacktestOut])
async def list_runs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(BacktestRun).order_by(desc(BacktestRun.started_at)).limit(limit)
        )
    ).all()
    return list(rows)


@router.get("/{run_id}", response_model=BacktestDetailOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(BacktestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return run
