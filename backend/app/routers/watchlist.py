from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.models import WatchlistItem, Stock, StockMomentum
from app.schemas.schemas import WatchlistAddRequest, WatchlistItemResponse, WatchlistListResponse
from app.services.momentum import get_stock_basket_breakdown, empty_basket_breakdown

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


async def _build_response(db: AsyncSession, item: WatchlistItem) -> WatchlistItemResponse:
    stock_result = await db.execute(select(Stock).where(Stock.ticker == item.ticker))
    stock = stock_result.scalar_one_or_none()

    if stock is None:
        return WatchlistItemResponse(
            ticker=item.ticker,
            company_name=None,
            momentum_score=None,
            added_at=item.added_at,
            baskets=empty_basket_breakdown(),
        )

    momentum_result = await db.execute(select(StockMomentum).where(StockMomentum.stock_id == stock.id))
    momentum = momentum_result.scalar_one_or_none()

    return WatchlistItemResponse(
        ticker=item.ticker,
        company_name=stock.company_name,
        momentum_score=momentum.score if momentum else None,
        added_at=item.added_at,
        baskets=await get_stock_basket_breakdown(db, stock.id),
    )


@router.get("", response_model=WatchlistListResponse)
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchlistItem).order_by(desc(WatchlistItem.added_at)))
    items = result.scalars().all()
    return {"items": [await _build_response(db, item) for item in items]}


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def add_to_watchlist(request: WatchlistAddRequest, db: AsyncSession = Depends(get_db)):
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    existing = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"{ticker} is already on the watchlist")

    item = WatchlistItem(ticker=ticker)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return await _build_response(db, item)


@router.delete("/{ticker}", status_code=204)
async def remove_from_watchlist(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.ticker == ticker.upper()))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Ticker not on watchlist")
    await db.delete(item)
    await db.commit()
