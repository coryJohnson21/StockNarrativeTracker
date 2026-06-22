from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Literal, Optional

from app.database import get_db
from app.models.models import Theme, ThemeMomentum, ThemeMention, ThemeProfile
from app.schemas.schemas import ThemeMomentumResponse, ThemeListResponse
from app.services.momentum import (
    get_trending_themes_by_category,
    get_theme_mention_breakdown,
    get_top_stocks_for_theme,
    FILING_SOURCE_TYPES,
)
from app.services.extraction import generate_theme_description

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("/trending", response_model=ThemeListResponse)
async def get_trending_themes(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0.0),
    category: Optional[Literal["filing", "media"]] = Query(
        None, description="Filter to 'filing' (10-K/10-Q/8-K/earnings calls) or 'media' (YouTube, transcripts, etc.)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Return themes sorted by momentum score, optionally scoped to one source category."""
    if category is not None:
        rows, total = await get_trending_themes_by_category(db, category, limit, offset, min_score)
        results = [
            ThemeMomentumResponse(
                id=row["parent"].id,
                name=row["parent"].name,
                description=row["parent"].description,
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
        return {"themes": results, "total": total}

    q = (
        select(Theme, ThemeMomentum)
        .join(ThemeMomentum, Theme.id == ThemeMomentum.theme_id)
        .where(ThemeMomentum.score >= min_score)
        .order_by(desc(ThemeMomentum.score))
    )

    count_q = (
        select(func.count())
        .select_from(Theme)
        .join(ThemeMomentum, Theme.id == ThemeMomentum.theme_id)
        .where(ThemeMomentum.score >= min_score)
    )

    total = (await db.execute(count_q)).scalar()
    rows = (await db.execute(q.offset(offset).limit(limit))).all()

    results = []
    for theme, momentum in rows:
        results.append(
            ThemeMomentumResponse(
                id=theme.id,
                name=theme.name,
                description=theme.description,
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

    return {"themes": results, "total": total}


@router.get("/{theme_name}/mentions")
async def get_theme_mentions(
    theme_name: str,
    limit: int = Query(20, le=100),
    category: Optional[Literal["filing", "media"]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return recent mentions for a specific theme, optionally scoped to one source category."""
    theme_result = await db.execute(
        select(Theme).where(Theme.name == theme_name)
    )
    theme = theme_result.scalar_one_or_none()
    if theme is None:
        return {"mentions": [], "theme": theme_name}

    from app.models.models import Source
    from sqlalchemy import desc as _desc

    q = (
        select(ThemeMention, Source)
        .join(Source, ThemeMention.source_id == Source.id)
        .where(ThemeMention.theme_id == theme.id)
        .order_by(_desc(ThemeMention.mentioned_at))
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
            "sentiment_score": mention.sentiment_score,
            "context": mention.context,
            "mentioned_at": mention.mentioned_at,
        }
        for mention, src in rows
    ]

    return {"theme": theme_name, "mentions": mentions}


@router.get("/{theme_name}/profile")
async def get_theme_profile(theme_name: str, db: AsyncSession = Depends(get_db)):
    """Landing-page data for a theme: an AI-generated definition (cached), our momentum
    score, a mention/sentiment breakdown by source category, and the stocks most
    associated with this theme."""
    theme_result = await db.execute(select(Theme).where(Theme.name == theme_name))
    theme = theme_result.scalar_one_or_none()
    if theme is None:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_name}' not found")

    profile_result = await db.execute(select(ThemeProfile).where(ThemeProfile.theme_id == theme.id))
    profile = profile_result.scalar_one_or_none()

    if profile is not None:
        description = profile.description
    else:
        description = await generate_theme_description(theme.name)
        profile = ThemeProfile(theme_id=theme.id, description=description)
        db.add(profile)
        await db.commit()

    momentum_result = await db.execute(select(ThemeMomentum).where(ThemeMomentum.theme_id == theme.id))
    momentum = momentum_result.scalar_one_or_none()

    mention_breakdown = await get_theme_mention_breakdown(db, theme.id)
    top_stocks = await get_top_stocks_for_theme(db, theme.id)

    return {
        "name": theme.name,
        "description": description,
        "momentum_score": momentum.score if momentum else None,
        "mention_breakdown": mention_breakdown,
        "top_stocks": top_stocks,
    }
