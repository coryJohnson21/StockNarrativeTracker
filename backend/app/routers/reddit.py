import re
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, distinct

from app.database import get_db
from app.models.models import RedditFeed, Source, Stock, StockMention
from app.schemas.schemas import (
    RedditFeedAddRequest,
    RedditFeedResponse,
    RedditFeedListResponse,
    RedditFeedDetailResponse,
    RedditPostResponse,
    RedditTopTicker,
    RedditOverviewResponse,
)
from app.services.reliability import DEFAULT_HORIZON, channel_track_record
from app.tasks.reddit_poll import poll_subreddit

router = APIRouter(prefix="/reddit", tags=["reddit"])

_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,50}$")

# How far back the overview page's "what is Reddit talking about" panel looks.
TRAILING_DAYS = 7
TOP_TICKERS_LIMIT = 3


def _channel(subreddit: str) -> str:
    """Sources ingested from a subreddit are stamped with this channel (see
    tasks/reddit_poll.py), which is also the key reliability scoring groups by."""
    return f"r/{subreddit}"


async def _top_tickers(
    db: AsyncSession,
    *,
    channels: list[str] | None = None,
    since: datetime | None = None,
    limit: int = 10,
) -> list[RedditTopTicker]:
    """Tickers mentioned by Reddit posts, most-mentioned first.

    `channels` scopes it to specific subreddits (omitted = every Reddit source), and
    `since` bounds it to recent mentions. Ranked by raw mention count with the number
    of distinct posts alongside, so one post naming a ticker ten times is visibly
    different from ten posts naming it once."""
    q = (
        select(
            Stock.ticker,
            Stock.company_name,
            Stock.symbol_status,
            func.count(StockMention.id).label("mention_count"),
            func.count(distinct(StockMention.source_id)).label("unique_posts"),
            func.avg(StockMention.sentiment_score).label("avg_sentiment"),
        )
        .join(Source, StockMention.source_id == Source.id)
        .join(Stock, StockMention.stock_id == Stock.id)
        .where(Source.type == "reddit")
        .group_by(Stock.id, Stock.ticker, Stock.company_name, Stock.symbol_status)
        .order_by(desc("mention_count"), desc("unique_posts"))
        .limit(limit)
    )
    if channels is not None:
        q = q.where(Source.channel.in_(channels))
    if since is not None:
        q = q.where(StockMention.mentioned_at >= since)

    rows = (await db.execute(q)).all()
    return [
        RedditTopTicker(
            ticker=row.ticker,
            company_name=row.company_name,
            symbol_status=row.symbol_status,
            mention_count=row.mention_count or 0,
            unique_posts=row.unique_posts or 0,
            avg_sentiment=round(row.avg_sentiment, 2) if row.avg_sentiment is not None else None,
        )
        for row in rows
    ]


async def _build_response(db: AsyncSession, feed: RedditFeed) -> RedditFeedResponse:
    count = (
        await db.execute(
            select(func.count(Source.id)).where(Source.channel == _channel(feed.subreddit))
        )
    ).scalar() or 0
    return RedditFeedResponse(
        id=feed.id,
        subreddit=feed.subreddit,
        last_polled_at=feed.last_polled_at,
        created_at=feed.created_at,
        post_count=count,
    )


async def _get_feed_or_404(db: AsyncSession, feed_id: str) -> RedditFeed:
    result = await db.execute(select(RedditFeed).where(RedditFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    return feed


@router.get("", response_model=RedditFeedListResponse)
async def list_feeds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RedditFeed).order_by(desc(RedditFeed.created_at)))
    feeds = result.scalars().all()
    return {"feeds": [await _build_response(db, f) for f in feeds]}


@router.get("/overview", response_model=RedditOverviewResponse)
async def get_overview(db: AsyncSession = Depends(get_db)):
    """Everything the Reddit landing page needs: the subscribed subreddits and the
    tickers Reddit has been talking about over the trailing week."""
    result = await db.execute(select(RedditFeed).order_by(desc(RedditFeed.created_at)))
    feeds = [await _build_response(db, f) for f in result.scalars().all()]

    since = datetime.utcnow() - timedelta(days=TRAILING_DAYS)
    return RedditOverviewResponse(
        feeds=feeds,
        total_posts=sum(f.post_count for f in feeds),
        top_tickers_7d=await _top_tickers(db, since=since, limit=TOP_TICKERS_LIMIT),
        trailing_days=TRAILING_DAYS,
    )


@router.post("", response_model=RedditFeedResponse, status_code=201)
async def add_feed(request: RedditFeedAddRequest, db: AsyncSession = Depends(get_db)):
    sub = request.subreddit.strip().lstrip("r/").lstrip("/")
    if not _SUBREDDIT_RE.match(sub):
        raise HTTPException(status_code=400, detail="Invalid subreddit name")

    existing = await db.execute(select(RedditFeed).where(RedditFeed.subreddit == sub))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Already subscribed to this subreddit")

    feed = RedditFeed(subreddit=sub)
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return await _build_response(db, feed)


@router.get("/{feed_id}", response_model=RedditFeedDetailResponse)
async def get_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    """One subreddit's landing page: its ingested posts, newest first, each with its
    AI summary embedded, plus the tickers this subreddit talks about most."""
    feed = await _get_feed_or_404(db, feed_id)
    base = await _build_response(db, feed)
    channel = _channel(feed.subreddit)

    sources_result = await db.execute(
        select(Source)
        .where(Source.channel == channel)
        .order_by(desc(func.coalesce(Source.published_at, Source.created_at)))
    )
    posts = [
        RedditPostResponse(
            id=source.id,
            title=source.title,
            url=source.url,
            published_at=source.published_at,
            created_at=source.created_at,
            status=source.status,
            error_message=source.error_message,
            summary=(source.source_metadata or {}).get("summary"),
        )
        for source in sources_result.scalars().all()
    ]

    return RedditFeedDetailResponse(
        **base.model_dump(),
        posts=posts,
        top_tickers=await _top_tickers(db, channels=[channel]),
    )


@router.get("/{feed_id}/track-record")
async def get_feed_track_record(
    feed_id: str,
    horizon: int = Query(DEFAULT_HORIZON, ge=1, le=250, description="Trading days after a call over which it is judged"),
    db: AsyncSession = Depends(get_db),
):
    """This subreddit's scored calls -- how often the crowd here was actually right.
    Computed on demand from stored calls and prices, the same way podcast feeds are,
    so both landing pages report a track record on identical terms."""
    feed = await _get_feed_or_404(db, feed_id)
    return await channel_track_record(db, _channel(feed.subreddit), horizon=horizon)


@router.delete("/{feed_id}", status_code=204)
async def remove_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    feed = await _get_feed_or_404(db, feed_id)
    await db.delete(feed)
    await db.commit()


@router.post("/{feed_id}/poll")
async def poll_now(feed_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    await _get_feed_or_404(db, feed_id)
    background_tasks.add_task(poll_subreddit, feed_id)
    return {"status": "started", "detail": "Fetching new posts in the background"}
