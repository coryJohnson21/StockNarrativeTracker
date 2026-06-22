from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, distinct, case, desc
from app.models.models import (
    Stock, Theme, StockMention, ThemeMention,
    StockMomentum, ThemeMomentum, Source,
)

# Press releases & earnings transcripts vs. general media coverage (CNBC, Bloomberg,
# YouTube, podcasts, pasted transcripts). Everything not explicitly a filing/earnings
# type is treated as media.
FILING_SOURCE_TYPES = ("10-K", "10-Q", "8-K", "earnings_call")


def _compute_score(
    total_mentions: int,
    recent_7d: int,
    older_30d: int,
    avg_sentiment: float,
    unique_sources: int,
    max_total_mentions: int,
) -> float:
    """
    Weighted momentum score (0–100).
    - 30% mention frequency (normalized)
    - 30% growth rate (recent vs older)
    - 25% sentiment
    - 15% cross-source diversity
    """
    freq = min(total_mentions / max(max_total_mentions, 1), 1.0)

    if older_30d == 0:
        growth = 1.0 if recent_7d > 0 else 0.5
    else:
        raw_growth = (recent_7d - older_30d / 4) / (older_30d / 4)
        growth = min(max((raw_growth + 1) / 2, 0.0), 1.0)

    sentiment_norm = (avg_sentiment + 100) / 200.0

    cross = min(unique_sources / 5.0, 1.0)

    score = (0.30 * freq + 0.30 * growth + 0.25 * sentiment_norm + 0.15 * cross) * 100
    return round(min(max(score, 0), 100), 1)


async def refresh_stock_momentum(db: AsyncSession) -> None:
    """Recompute momentum for all stocks."""
    now = datetime.utcnow()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    stocks_result = await db.execute(select(Stock))
    stocks = stocks_result.scalars().all()

    # Max total mentions for normalization
    max_q = await db.execute(
        select(func.count(StockMention.id)).group_by(StockMention.stock_id)
    )
    max_mentions = max((row[0] for row in max_q), default=1)

    for stock in stocks:
        total_q = await db.execute(
            select(func.count(StockMention.id)).where(StockMention.stock_id == stock.id)
        )
        total = total_q.scalar() or 0

        recent_q = await db.execute(
            select(func.count(StockMention.id)).where(
                and_(StockMention.stock_id == stock.id, StockMention.mentioned_at >= cutoff_7d)
            )
        )
        recent = recent_q.scalar() or 0

        older_q = await db.execute(
            select(func.count(StockMention.id)).where(
                and_(StockMention.stock_id == stock.id, StockMention.mentioned_at >= cutoff_30d)
            )
        )
        older = older_q.scalar() or 0

        sentiment_q = await db.execute(
            select(func.avg(StockMention.sentiment_score)).where(
                StockMention.stock_id == stock.id
            )
        )
        avg_sent = sentiment_q.scalar() or 0.0

        sources_q = await db.execute(
            select(func.count(distinct(StockMention.source_id))).where(
                StockMention.stock_id == stock.id
            )
        )
        unique_src = sources_q.scalar() or 0

        growth_rate = ((recent - (older / 4)) / max(older / 4, 1)) if older > 0 else (1.0 if recent > 0 else 0.0)
        score = _compute_score(total, recent, older, avg_sent, unique_src, max_mentions)

        existing = await db.execute(
            select(StockMomentum).where(StockMomentum.stock_id == stock.id)
        )
        momentum = existing.scalar_one_or_none()

        if momentum is None:
            momentum = StockMomentum(stock_id=stock.id)
            db.add(momentum)

        momentum.score = score
        momentum.mention_count = total
        momentum.mention_count_7d = recent
        momentum.mention_count_30d = older
        momentum.mention_growth_rate = round(growth_rate, 3)
        momentum.avg_sentiment = round(avg_sent, 1)
        momentum.unique_sources = unique_src
        momentum.computed_at = now

    await db.commit()


async def _trending_by_category(
    db: AsyncSession,
    mention_model,
    parent_model,
    parent_id_col,
    mention_fk_col,
    category: str,
    limit: int,
    offset: int,
    min_score: float,
) -> tuple[list[dict], int]:
    """Live-aggregate momentum for one category (filing vs. media) without touching
    the precomputed momentum tables, which stay aggregate-across-everything."""
    now = datetime.utcnow()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    type_filter = (
        Source.type.in_(FILING_SOURCE_TYPES)
        if category == "filing"
        else Source.type.notin_(FILING_SOURCE_TYPES)
    )

    q = (
        select(
            parent_model,
            func.count(mention_model.id).label("total"),
            func.sum(case((mention_model.mentioned_at >= cutoff_7d, 1), else_=0)).label("recent_7d"),
            func.sum(case((mention_model.mentioned_at >= cutoff_30d, 1), else_=0)).label("recent_30d"),
            func.avg(mention_model.sentiment_score).label("avg_sentiment"),
            func.count(distinct(mention_model.source_id)).label("unique_sources"),
        )
        .join(mention_model, mention_fk_col == parent_id_col)
        .join(Source, mention_model.source_id == Source.id)
        .where(type_filter)
        .group_by(parent_id_col)
    )

    rows = (await db.execute(q)).all()
    max_total = max((row.total for row in rows), default=1)

    results = []
    for row in rows:
        parent = row[0]
        total = row.total or 0
        recent = row.recent_7d or 0
        older = row.recent_30d or 0
        avg_sent = row.avg_sentiment or 0.0
        unique_src = row.unique_sources or 0

        growth_rate = ((recent - (older / 4)) / max(older / 4, 1)) if older > 0 else (1.0 if recent > 0 else 0.0)
        score = _compute_score(total, recent, older, avg_sent, unique_src, max_total)

        if score < min_score:
            continue

        results.append(
            {
                "parent": parent,
                "score": score,
                "mention_count": total,
                "mention_count_7d": recent,
                "mention_count_30d": older,
                "mention_growth_rate": round(growth_rate, 3),
                "avg_sentiment": round(avg_sent, 1),
                "unique_sources": unique_src,
                "ai_summary": None,
                "computed_at": now,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    total_count = len(results)
    return results[offset:offset + limit], total_count


async def get_trending_stocks_by_category(
    db: AsyncSession, category: str, limit: int = 50, offset: int = 0, min_score: float = 0.0
) -> tuple[list[dict], int]:
    return await _trending_by_category(
        db, StockMention, Stock, Stock.id, StockMention.stock_id, category, limit, offset, min_score
    )


async def get_trending_themes_by_category(
    db: AsyncSession, category: str, limit: int = 50, offset: int = 0, min_score: float = 0.0
) -> tuple[list[dict], int]:
    return await _trending_by_category(
        db, ThemeMention, Theme, Theme.id, ThemeMention.theme_id, category, limit, offset, min_score
    )


async def get_stock_mention_breakdown(db: AsyncSession, stock_id) -> dict:
    """Per-category (filing vs. media) mention count, sentiment, and source diversity
    for a single stock — used on the stock landing page."""
    breakdown = {}
    for category in ("filing", "media"):
        type_filter = (
            Source.type.in_(FILING_SOURCE_TYPES)
            if category == "filing"
            else Source.type.notin_(FILING_SOURCE_TYPES)
        )
        q = (
            select(
                func.count(StockMention.id).label("total"),
                func.avg(StockMention.sentiment_score).label("avg_sentiment"),
                func.count(distinct(StockMention.source_id)).label("unique_sources"),
            )
            .join(Source, StockMention.source_id == Source.id)
            .where(StockMention.stock_id == stock_id, type_filter)
        )
        row = (await db.execute(q)).one()
        breakdown[category] = {
            "mention_count": row.total or 0,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
            "unique_sources": row.unique_sources or 0,
        }
    return breakdown


async def get_theme_mention_breakdown(db: AsyncSession, theme_id) -> dict:
    """Per-category (filing vs. media) mention count, sentiment, and source diversity
    for a single theme — used on the theme landing page."""
    breakdown = {}
    for category in ("filing", "media"):
        type_filter = (
            Source.type.in_(FILING_SOURCE_TYPES)
            if category == "filing"
            else Source.type.notin_(FILING_SOURCE_TYPES)
        )
        q = (
            select(
                func.count(ThemeMention.id).label("total"),
                func.avg(ThemeMention.sentiment_score).label("avg_sentiment"),
                func.count(distinct(ThemeMention.source_id)).label("unique_sources"),
            )
            .join(Source, ThemeMention.source_id == Source.id)
            .where(ThemeMention.theme_id == theme_id, type_filter)
        )
        row = (await db.execute(q)).one()
        breakdown[category] = {
            "mention_count": row.total or 0,
            "avg_sentiment": round(row.avg_sentiment or 0.0, 1),
            "unique_sources": row.unique_sources or 0,
        }
    return breakdown


async def get_stock_mention_contexts(db: AsyncSession, stock_id, category: str, limit: int = 6) -> list[str]:
    """Sample of recent mention context quotes for one category, used to ground the
    narrative-synthesis prompt in what was actually said rather than just aggregate scores."""
    type_filter = (
        Source.type.in_(FILING_SOURCE_TYPES)
        if category == "filing"
        else Source.type.notin_(FILING_SOURCE_TYPES)
    )
    q = (
        select(StockMention.context)
        .join(Source, StockMention.source_id == Source.id)
        .where(StockMention.stock_id == stock_id, type_filter, StockMention.context.isnot(None))
        .order_by(desc(StockMention.mentioned_at))
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    return [row[0] for row in rows if row[0]]


async def get_top_stocks_for_theme(db: AsyncSession, theme_id, limit: int = 8) -> list[dict]:
    """Stocks most often mentioned in the same sources as this theme (co-mention count)."""
    q = (
        select(
            Stock.ticker,
            Stock.company_name,
            func.count(distinct(StockMention.source_id)).label("co_mentions"),
        )
        .join(StockMention, StockMention.stock_id == Stock.id)
        .join(ThemeMention, ThemeMention.source_id == StockMention.source_id)
        .where(ThemeMention.theme_id == theme_id)
        .group_by(Stock.id)
        .order_by(desc("co_mentions"))
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    return [
        {"ticker": row.ticker, "company_name": row.company_name, "co_mentions": row.co_mentions}
        for row in rows
    ]


async def refresh_theme_momentum(db: AsyncSession) -> None:
    """Recompute momentum for all themes."""
    now = datetime.utcnow()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    themes_result = await db.execute(select(Theme))
    themes = themes_result.scalars().all()

    max_q = await db.execute(
        select(func.count(ThemeMention.id)).group_by(ThemeMention.theme_id)
    )
    max_mentions = max((row[0] for row in max_q), default=1)

    for theme in themes:
        total_q = await db.execute(
            select(func.count(ThemeMention.id)).where(ThemeMention.theme_id == theme.id)
        )
        total = total_q.scalar() or 0

        recent_q = await db.execute(
            select(func.count(ThemeMention.id)).where(
                and_(ThemeMention.theme_id == theme.id, ThemeMention.mentioned_at >= cutoff_7d)
            )
        )
        recent = recent_q.scalar() or 0

        older_q = await db.execute(
            select(func.count(ThemeMention.id)).where(
                and_(ThemeMention.theme_id == theme.id, ThemeMention.mentioned_at >= cutoff_30d)
            )
        )
        older = older_q.scalar() or 0

        sentiment_q = await db.execute(
            select(func.avg(ThemeMention.sentiment_score)).where(
                ThemeMention.theme_id == theme.id
            )
        )
        avg_sent = sentiment_q.scalar() or 0.0

        sources_q = await db.execute(
            select(func.count(distinct(ThemeMention.source_id))).where(
                ThemeMention.theme_id == theme.id
            )
        )
        unique_src = sources_q.scalar() or 0

        growth_rate = ((recent - (older / 4)) / max(older / 4, 1)) if older > 0 else (1.0 if recent > 0 else 0.0)
        score = _compute_score(total, recent, older, avg_sent, unique_src, max_mentions)

        existing = await db.execute(
            select(ThemeMomentum).where(ThemeMomentum.theme_id == theme.id)
        )
        momentum = existing.scalar_one_or_none()

        if momentum is None:
            momentum = ThemeMomentum(theme_id=theme.id)
            db.add(momentum)

        momentum.score = score
        momentum.mention_count = total
        momentum.mention_count_7d = recent
        momentum.mention_count_30d = older
        momentum.mention_growth_rate = round(growth_rate, 3)
        momentum.avg_sentiment = round(avg_sent, 1)
        momentum.unique_sources = unique_src
        momentum.computed_at = now

    await db.commit()
