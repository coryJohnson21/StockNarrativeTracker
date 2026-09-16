from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.models import PodcastFeed, Source
from app.schemas.schemas import (
    PodcastFeedAddRequest,
    PodcastFeedResponse,
    PodcastFeedListResponse,
    PodcastFeedDetailResponse,
    PodcastEpisodeResponse,
)
from app.services import podcast as podcast_service
from app.services import youtube as youtube_service
from app.tasks.podcast_poll import poll_feed, poll_all_feeds

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


@router.get("/search")
async def search_podcasts(q: str = Query(..., min_length=1)):
    """Look up podcasts by name and return their RSS feed URLs, so the user can
    subscribe by show name instead of finding the raw feed URL themselves."""
    results = await podcast_service.search_podcasts(q)
    return {"results": results}


@router.get("/resolve-youtube-channel")
async def resolve_youtube_channel(url: str = Query(..., min_length=1)):
    """Resolve a YouTube channel URL or @handle to its uploads feed, so subscribing
    to a channel works the same way as subscribing to a podcast RSS feed -- new
    videos are auto-ingested via captions (falling back to Whisper) instead of
    downloading and transcribing podcast audio."""
    result = await youtube_service.resolve_channel(url)
    if result is None:
        raise HTTPException(status_code=404, detail="Could not resolve that as a YouTube channel")
    return result


async def _build_response(db: AsyncSession, feed: PodcastFeed) -> PodcastFeedResponse:
    row = (
        await db.execute(
            select(
                func.count(Source.id),
                func.max(func.coalesce(Source.published_at, Source.created_at)),
            ).where(Source.channel == feed.label)
        )
    ).one()
    return PodcastFeedResponse(
        id=feed.id,
        url=feed.url,
        label=feed.label,
        source_type=feed.source_type,
        last_polled_at=feed.last_polled_at,
        created_at=feed.created_at,
        episode_count=row[0] or 0,
        latest_episode_at=row[1],
    )


@router.get("", response_model=PodcastFeedListResponse)
async def list_feeds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PodcastFeed).order_by(desc(PodcastFeed.created_at)))
    feeds = result.scalars().all()
    return {"feeds": [await _build_response(db, f) for f in feeds]}


@router.post("", response_model=PodcastFeedResponse, status_code=201)
async def add_feed(request: PodcastFeedAddRequest, db: AsyncSession = Depends(get_db)):
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Feed URL is required")

    existing = await db.execute(select(PodcastFeed).where(PodcastFeed.url == url))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="This feed is already subscribed")

    feed = PodcastFeed(url=url, label=request.label.strip(), source_type=request.source_type)
    db.add(feed)
    await db.commit()
    await db.refresh(feed)

    return await _build_response(db, feed)


@router.get("/{feed_id}", response_model=PodcastFeedDetailResponse)
async def get_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    """Feed details plus every ingested episode/video for it, newest first, each
    with its AI summary already embedded so the landing page doesn't need a
    separate fetch per episode just to show what it was about."""
    result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")

    base = await _build_response(db, feed)

    sources_result = await db.execute(
        select(Source)
        .where(Source.channel == feed.label)
        .order_by(desc(func.coalesce(Source.published_at, Source.created_at)))
    )
    sources = sources_result.scalars().all()

    episodes = [
        PodcastEpisodeResponse(
            id=source.id,
            title=source.title,
            published_at=source.published_at,
            status=source.status,
            duration_seconds=source.duration_seconds,
            error_message=source.error_message,
            summary=(source.source_metadata or {}).get("summary"),
        )
        for source in sources
    ]

    return PodcastFeedDetailResponse(**base.model_dump(), episodes=episodes)


@router.delete("/{feed_id}", status_code=204)
async def remove_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    await db.commit()


@router.post("/{feed_id}/poll")
async def poll_now(feed_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Check this feed for new episodes right now instead of waiting for the
    periodic poller."""
    result = await db.execute(select(PodcastFeed).where(PodcastFeed.id == feed_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Feed not found")

    background_tasks.add_task(poll_feed, feed_id)
    return {"status": "started", "detail": "Checking feed for new episodes in the background"}


@router.post("/poll-all")
async def poll_all_now(background_tasks: BackgroundTasks):
    """Check every subscribed feed for new episodes right now instead of waiting
    for the periodic poller."""
    background_tasks.add_task(poll_all_feeds)
    return {"status": "started", "detail": "Checking all feeds for new episodes in the background"}
