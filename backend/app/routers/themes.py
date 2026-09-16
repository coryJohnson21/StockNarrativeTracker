from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Literal, Optional

from app.database import get_db
from app.models.models import Theme, ThemeMomentum, ThemeMention, ThemeProfile
from app.schemas.schemas import ThemeMomentumResponse, ThemeListResponse, ThemeTrackRequest
from app.services.momentum import (
    get_trending_themes_by_category,
    get_trending_themes_by_channel,
    get_theme_mention_breakdown,
    get_top_stocks_for_theme,
    get_theme_momentum_extras,
    sentiment_to_label,
    FILING_SOURCE_TYPES,
)
from app.services.extraction import generate_theme_description, generate_theme_impact_analysis
from app.services.theme_index import get_theme_index

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("/trending", response_model=ThemeListResponse)
async def get_trending_themes(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0.0),
    category: Optional[Literal["filing", "media"]] = Query(
        None, description="Filter to 'filing' (10-K/10-Q/8-K/earnings calls) or 'media' (YouTube, transcripts, etc.)"
    ),
    channel: Optional[Literal["youtube", "podcast", "news", "reddit", "x"]] = Query(
        None, description="Filter to a specific media channel within the 'media' category"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Return themes sorted by momentum score, optionally scoped to one source category or channel."""
    if channel is not None:
        rows, total = await get_trending_themes_by_channel(db, channel, limit, offset, min_score)
    elif category is not None:
        rows, total = await get_trending_themes_by_category(db, category, limit, offset, min_score)
    else:
        rows = None

    if rows is not None:
        theme_ids = [row["parent"].id for row in rows]
        extras = await get_theme_momentum_extras(db, theme_ids)
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
                label=sentiment_to_label(row["avg_sentiment"]),
                previous_label=extras.get(row["parent"].id, {}).get("previous_label"),
                computed_at=row["computed_at"],
            )
            for row in rows
        ]
        return {"themes": results, "total": total}

    q = (
        select(Theme, ThemeMomentum)
        .join(ThemeMomentum, Theme.id == ThemeMomentum.theme_id)
        .where(ThemeMomentum.score >= min_score, Theme.is_tracked.is_(True))
        .order_by(desc(ThemeMomentum.score))
    )

    count_q = (
        select(func.count())
        .select_from(Theme)
        .join(ThemeMomentum, Theme.id == ThemeMomentum.theme_id)
        .where(ThemeMomentum.score >= min_score, Theme.is_tracked.is_(True))
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
                label=momentum.label,
                previous_label=momentum.previous_label,
                computed_at=momentum.computed_at,
            )
        )

    return {"themes": results, "total": total}


@router.post("/track", status_code=201)
async def track_theme(request: ThemeTrackRequest, db: AsyncSession = Depends(get_db)):
    """Add a theme to the curated tracked list. If the name matches an existing theme
    (case-insensitive) it's promoted from the untracked candidate pool; otherwise a new
    Theme row is created, tracked from the start, with a zeroed momentum row so it shows
    up immediately instead of waiting for the next ingestion's momentum refresh."""
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Theme name is required")

    result = await db.execute(select(Theme).where(func.lower(Theme.name) == name.lower()))
    theme = result.scalar_one_or_none()

    if theme is not None and theme.is_tracked:
        raise HTTPException(status_code=409, detail=f"'{theme.name}' is already tracked")

    if theme is None:
        theme = Theme(name=name, is_tracked=True)
        db.add(theme)
        await db.flush()
        db.add(ThemeMomentum(theme_id=theme.id))
    else:
        theme.is_tracked = True

    await db.commit()
    return {"name": theme.name, "is_tracked": True}


@router.delete("/track/{theme_name}", status_code=204)
async def untrack_theme(theme_name: str, db: AsyncSession = Depends(get_db)):
    """Remove a theme from the tracked list. Soft-untrack only -- all historical
    mentions, momentum, and profile data are kept, so re-tracking later restores it."""
    result = await db.execute(select(Theme).where(Theme.name == theme_name))
    theme = result.scalar_one_or_none()
    if theme is None or not theme.is_tracked:
        raise HTTPException(status_code=404, detail=f"'{theme_name}' is not on the tracked list")

    theme.is_tracked = False
    await db.commit()


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

    if profile.impact_analysis is not None:
        impact_analysis = profile.impact_analysis
    else:
        known_themes_result = await db.execute(select(Theme.name).where(Theme.id != theme.id))
        known_themes = [name for (name,) in known_themes_result.all()]
        impact_analysis = await generate_theme_impact_analysis(theme.name, known_themes)
        profile.impact_analysis = impact_analysis
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
        "impact_analysis": impact_analysis,
    }


@router.get("/{theme_name}/index")
async def get_theme_index_endpoint(
    theme_name: str,
    days: int = Query(90, ge=30, le=730),
    db: AsyncSession = Depends(get_db),
):
    """Equal-weight return index of the theme's most co-mentioned stocks (base 100),
    joined week by week to the theme's mention volume and sentiment, with lead/lag
    rank correlations so 'the narrative peaked' becomes checkable against the basket."""
    theme = (await db.execute(select(Theme).where(Theme.name == theme_name))).scalar_one_or_none()
    if theme is None:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_name}' not found")
    return await get_theme_index(db, theme, days=days)
