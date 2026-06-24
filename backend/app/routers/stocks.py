from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import Literal, Optional

from app.database import get_db
from app.models.models import Stock, StockMomentum, StockMention, StockProfile, StockNarrative
from app.schemas.schemas import StockMomentumResponse, StockListResponse
from app.services.momentum import (
    get_trending_stocks_by_category,
    get_stock_mention_breakdown,
    get_stock_self_vs_external_breakdown,
    get_stock_mention_contexts,
    get_stock_mention_history,
    FILING_SOURCE_TYPES,
)
from app.services import market_data
from app.services.extraction import condense_company_description, generate_narrative_summary

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/trending", response_model=StockListResponse)
async def get_trending_stocks(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0.0),
    category: Optional[Literal["filing", "media"]] = Query(
        None, description="Filter to 'filing' (10-K/10-Q/8-K/earnings calls) or 'media' (YouTube, transcripts, etc.)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Return stocks sorted by momentum score, optionally scoped to one source category."""
    if category is not None:
        rows, total = await get_trending_stocks_by_category(db, category, limit, offset, min_score)
        results = [
            StockMomentumResponse(
                id=row["parent"].id,
                ticker=row["parent"].ticker,
                company_name=row["parent"].company_name,
                sector=row["parent"].sector,
                score=row["score"],
                mention_count=row["mention_count"],
                mention_count_7d=row["mention_count_7d"],
                mention_count_30d=row["mention_count_30d"],
                mention_growth_rate=row["mention_growth_rate"],
                avg_sentiment=row["avg_sentiment"],
                unique_sources=row["unique_sources"],
                ai_summary=row["ai_summary"],
                computed_at=row["computed_at"],
            )
            for row in rows
        ]
        return {"stocks": results, "total": total}

    q = (
        select(Stock, StockMomentum)
        .join(StockMomentum, Stock.id == StockMomentum.stock_id)
        .where(StockMomentum.score >= min_score)
        .order_by(desc(StockMomentum.score))
    )

    count_q = (
        select(func.count())
        .select_from(Stock)
        .join(StockMomentum, Stock.id == StockMomentum.stock_id)
        .where(StockMomentum.score >= min_score)
    )

    total = (await db.execute(count_q)).scalar()
    rows = (await db.execute(q.offset(offset).limit(limit))).all()

    results = []
    for stock, momentum in rows:
        results.append(
            StockMomentumResponse(
                id=stock.id,
                ticker=stock.ticker,
                company_name=stock.company_name,
                sector=stock.sector,
                score=momentum.score,
                mention_count=momentum.mention_count,
                mention_count_7d=momentum.mention_count_7d,
                mention_count_30d=momentum.mention_count_30d,
                mention_growth_rate=momentum.mention_growth_rate,
                avg_sentiment=momentum.avg_sentiment,
                unique_sources=momentum.unique_sources,
                ai_summary=momentum.ai_summary,
                computed_at=momentum.computed_at,
            )
        )

    return {"stocks": results, "total": total}


@router.get("/{ticker}/mentions")
async def get_stock_mentions(
    ticker: str,
    limit: int = Query(20, le=100),
    category: Optional[Literal["filing", "media"]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return recent mentions for a specific ticker, optionally scoped to one source category."""
    stock_result = await db.execute(
        select(Stock).where(Stock.ticker == ticker.upper())
    )
    stock = stock_result.scalar_one_or_none()
    if stock is None:
        return {"mentions": [], "ticker": ticker.upper()}

    from app.models.models import Source
    from sqlalchemy import desc as _desc

    q = (
        select(StockMention, Source)
        .join(Source, StockMention.source_id == Source.id)
        .where(StockMention.stock_id == stock.id)
        .order_by(_desc(StockMention.mentioned_at))
        .limit(limit)
    )
    if category == "filing":
        q = q.where(Source.type.in_(FILING_SOURCE_TYPES))
    elif category == "media":
        q = q.where(Source.type.notin_(FILING_SOURCE_TYPES))
    rows = (await db.execute(q)).all()

    mentions = [
        {
            "source_title": src.title,
            "source_type": src.type,
            "source_channel": src.channel,
            "source_url": src.url,
            "sentiment_score": mention.sentiment_score,
            "context": mention.context,
            "mentioned_at": mention.mentioned_at,
        }
        for mention, src in rows
    ]

    return {"ticker": ticker.upper(), "company": stock.company_name, "mentions": mentions}


@router.get("/{ticker}/price-history")
async def get_stock_price_history(
    ticker: str,
    range: Literal["1mo", "3mo", "6mo", "1y", "5y"] = Query("6mo"),
    db: AsyncSession = Depends(get_db),
):
    """Daily closing prices for the stock landing page chart, fetched live from Yahoo
    Finance (kept separate from /profile so the chart can be re-ranged without re-running
    the narrative synthesis)."""
    stock_result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = stock_result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not tracked")

    points = await market_data.fetch_price_history(stock.ticker, range_=range)
    return {"ticker": stock.ticker, "range": range, "points": points}


@router.get("/{ticker}/mention-history")
async def get_stock_mention_history_endpoint(
    ticker: str,
    range: Literal["1mo", "3mo", "6mo", "1y", "5y"] = Query("6mo"),
    db: AsyncSession = Depends(get_db),
):
    """Mention count + sentiment over time, bucketed from raw mention timestamps —
    powers the narrative momentum chart so users can see when the story built up,
    not just its current snapshot."""
    stock_result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = stock_result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not tracked")

    points = await get_stock_mention_history(db, stock.id, range_=range)
    return {"ticker": stock.ticker, "range": range, "points": points}


@router.get("/{ticker}/profile")
async def get_stock_profile(ticker: str, db: AsyncSession = Depends(get_db)):
    """Landing-page data for a stock: live price/fundamentals from Yahoo Finance, an
    AI-condensed company description (cached), our momentum score, and a breakdown of
    mention volume/sentiment by source category (filings vs. media)."""
    stock_result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = stock_result.scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} is not tracked")

    market = await market_data.fetch_market_data(stock.ticker)

    description = None
    profile_result = await db.execute(select(StockProfile).where(StockProfile.stock_id == stock.id))
    profile = profile_result.scalar_one_or_none()

    if profile is not None:
        description = profile.description
    elif market and market.get("business_summary"):
        description = await condense_company_description(
            stock.company_name or stock.ticker, market["business_summary"]
        )
        profile = StockProfile(stock_id=stock.id, description=description)
        db.add(profile)
        await db.commit()

    momentum_result = await db.execute(select(StockMomentum).where(StockMomentum.stock_id == stock.id))
    momentum = momentum_result.scalar_one_or_none()

    mention_breakdown = await get_stock_mention_breakdown(db, stock.id)
    self_vs_external_breakdown = await get_stock_self_vs_external_breakdown(db, stock.id)

    total_mentions = mention_breakdown["filing"]["mention_count"] + mention_breakdown["media"]["mention_count"]

    narrative_summary = None
    if total_mentions > 0:
        narrative_result = await db.execute(select(StockNarrative).where(StockNarrative.stock_id == stock.id))
        narrative = narrative_result.scalar_one_or_none()

        if narrative is not None and narrative.mention_count_snapshot == total_mentions:
            narrative_summary = narrative.summary
        else:
            filing_contexts = await get_stock_mention_contexts(db, stock.id, "filing")
            media_contexts = await get_stock_mention_contexts(db, stock.id, "media")
            narrative_summary = await generate_narrative_summary(
                stock.ticker,
                stock.company_name or stock.ticker,
                mention_breakdown["filing"]["avg_sentiment"],
                filing_contexts,
                mention_breakdown["media"]["avg_sentiment"],
                media_contexts,
            )
            if narrative is None:
                narrative = StockNarrative(stock_id=stock.id)
                db.add(narrative)
            narrative.summary = narrative_summary
            narrative.mention_count_snapshot = total_mentions
            await db.commit()

    return {
        "ticker": stock.ticker,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "description": description,
        "price": {
            "open": market.get("open_price") if market else None,
            "current": market.get("current_price") if market else None,
            "currency": market.get("currency") if market else None,
        },
        "fundamentals": {
            "market_cap": market.get("market_cap") if market else None,
            "pe_ratio": market.get("pe_ratio") if market else None,
            "price_to_book": market.get("price_to_book") if market else None,
            "price_to_sales": market.get("price_to_sales") if market else None,
        },
        "momentum_score": momentum.score if momentum else None,
        "mention_breakdown": mention_breakdown,
        "self_vs_external_breakdown": self_vs_external_breakdown,
        "narrative_summary": narrative_summary,
    }
