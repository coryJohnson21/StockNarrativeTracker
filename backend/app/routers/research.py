from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.services.research import get_research_status, refresh_research, run_backtest

router = APIRouter(prefix="/research", tags=["research"])


async def _refresh_in_background(full_prices: bool) -> None:
    async with AsyncSessionLocal() as db:
        await refresh_research(db, full_prices=full_prices)


@router.get("/status")
async def research_status(db: AsyncSession = Depends(get_db)):
    return await get_research_status(db)


@router.post("/refresh")
async def refresh(
    background_tasks: BackgroundTasks,
    full_prices: bool = Query(False, description="Re-pull a full year of prices for every stock, not just new ones"),
):
    """Pull daily closes and rebuild point-in-time momentum snapshots from the
    first mention to today. Runs in the background; poll /status."""
    background_tasks.add_task(_refresh_in_background, full_prices)
    return {"status": "started", "detail": "Refreshing prices and rebuilding momentum snapshots in the background"}


@router.get("/backtest")
async def backtest(
    horizon: int = Query(20, ge=1, le=250, description="Forward window in trading days"),
    buckets: int = Query(5, ge=2, le=10),
    min_mentions_7d: int = Query(1, ge=0, description="Only score days where the stock was actually being talked about"),
    db: AsyncSession = Depends(get_db),
):
    """Does the momentum score rank future returns? Equal-count score buckets with
    forward and SPY-excess returns, plus rank correlation (IC) for the score and each
    component, with a t-stat over per-date ICs so one lucky week can't carry it."""
    return await run_backtest(db, horizon=horizon, buckets=buckets, min_mentions_7d=min_mentions_7d)
