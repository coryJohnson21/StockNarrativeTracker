from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.insiders import (
    get_insider_overview,
    get_insider_status,
    get_recent_notable_trades,
    scan_insider_transactions,
)
from app.tasks.sec_scan import recent_window_since

router = APIRouter(prefix="/insiders", tags=["insiders"])


@router.get("/status")
async def insider_status(db: AsyncSession = Depends(get_db)):
    return await get_insider_status(db)


@router.get("/overview")
async def insider_overview(
    days: int = Query(30, ge=1, le=365, description="Trailing window by transaction date"),
    include_institutions: bool = Query(True, description="Include 10% holders (funds and holding entities)"),
    db: AsyncSession = Depends(get_db),
):
    """Market-wide buying and selling totals for the window, plus the companies
    where several insiders bought independently."""
    return await get_insider_overview(db, days=days, include_institutions=include_institutions)


@router.get("/recent")
async def recent_insider_trades(
    days: int = Query(30, ge=1, le=365, description="Trailing window by transaction date"),
    limit: int = Query(10, ge=1, le=50, description="Rows per side"),
    include_institutions: bool = Query(True, description="Include 10% holders (funds and holding entities)"),
    db: AsyncSession = Depends(get_db),
):
    """Largest open-market insider buys and sells in the recent window, ranked
    separately so the rarer purchases aren't buried under routine selling."""
    return await get_recent_notable_trades(db, days=days, limit=limit, include_institutions=include_institutions)


@router.post("/scan")
async def scan(
    background_tasks: BackgroundTasks,
    since: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to the last 30 days"),
    tickers: Optional[str] = Query(None, description="Comma-separated subset, e.g. AAPL,NVDA"),
):
    """Pull Form 4 insider transactions for the S&P 500 (or a subset). A full pass
    over several months is thousands of small SEC fetches; runs in the background."""
    since_date = since or recent_window_since(30)
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()] if tickers else None
    background_tasks.add_task(scan_insider_transactions, since_date, ticker_list)
    return {"status": "started", "detail": f"Scanning Form 4 filings since {since_date} in the background"}
